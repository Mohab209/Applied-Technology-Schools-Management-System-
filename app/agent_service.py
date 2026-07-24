import os
import re
import json
import operator
from typing import Annotated, Any, TypedDict
from dotenv import load_dotenv
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from sqlalchemy import select, or_, func
from langfuse.langchain import CallbackHandler
from app.database import SessionLocal
from app.models import School
from app.rag_service import answer_query as rag_answer_query
from app.utils import normalize_arabic

load_dotenv()

langfuse_handler = CallbackHandler()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env")

llm = ChatOpenAI(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    temperature=0,
)

@tool
def search_schools(names: list[str] | None = None, specialization: str | None = None, location: str | None = None, industrial_partner: str | None = None, minimum_score: int | None = None,) -> list[dict]:
    """
    Search and retrieve structured school records from the main database.

    Use this tool when you need basic, high-level attributes of Applied Technology Schools, such as:
    - Official Arabic or English school names
    - Geographic locations (cities/governorates)
    - Major academic specializations
    - Minimum required scores (admission cutoffs)
    - Industrial partners (companies/initiatives)
    - Accepted governorates, study duration, and official website links

    Parameters:
    - names: Optional list of school name keywords to filter by (e.g., ["ابدأ", "ارابكوميد"]).
    - specialization: Keyword to search in school specializations.
    - location: Keyword to search in school location or governorate.
    - industrial_partner: Keyword to search in industrial partners.
    - minimum_score: Minimum required score filter (returns schools with score >= minimum_score).

    Returns:
    - A list of dictionaries containing structured data for matching schools.
    """
    db = SessionLocal()
    try:
        stmt = select(School)

        if names:
            conditions = []
            for name in names:
                norm_name = normalize_arabic(name)
                norm_col = func.translate(School.arabic_name, 'أإآٱىة', 'اااايه')
                
                conditions.append(norm_col.ilike(f"%{norm_name}%"))
                conditions.append(School.english_name.ilike(f"%{name}%"))
            
            stmt = stmt.where(or_(*conditions))

        if specialization:
            norm_spec = normalize_arabic(specialization)
            norm_col = func.translate(School.specialization, 'أإآٱىة', 'اااايه')
            stmt = stmt.where(norm_col.ilike(f"%{norm_spec}%"))

        if location:
            norm_loc = normalize_arabic(location)
            norm_col = func.translate(School.location, 'أإآٱىة', 'اااايه')
            stmt = stmt.where(norm_col.ilike(f"%{norm_loc}%"))

        schools = db.execute(stmt).scalars().all()
        return [
            {
                "id": school.id,
                "arabic_name": school.arabic_name,
                "english_name": school.english_name,
                "location": school.location,
                "specialization": school.specialization,
                "minimum_score": school.minimum_score,
                "industrial_partner": school.industrial_partner,
                "accepted_governorates": school.accepted_governorates,
                "study_duration": school.study_duration,
                "official_website": school.official_website,
                "description": school.description,
            }
            for school in schools
        ]
    finally:
        db.close()

@tool
async def search_documents(question: str, school_id: int | None = None) -> str:
    """
    Search the uploaded PDF documents using RAG.

    Use this tool whenever the answer should come from uploaded PDF files.
    - If you are querying about a specific school and know its school_id, pass school_id.
    - If comparing multiple schools or asking a general question, leave school_id as None.
    """

    db = SessionLocal()

    try:
        result = await rag_answer_query(
            query=question,
            db=db,
            school_id=school_id,
            k=5,
        )

        return str(result.get("answer", "لم يتم العثور على إجابة في المستندات."))

    except Exception as e:
        return f"حدث خطأ أثناء البحث في المستندات: {str(e)}"
    finally:
        db.close()


# =====================================================
# Register Tools
# =====================================================

tools = [
    search_schools,
    search_documents,
]

llm_with_tools = llm.bind_tools(tools)


# =====================================================
# System Prompt
# =====================================================

SYSTEM_PROMPT = """
You are an AI Assistant for the Applied Technology Schools Management System in Egypt.

Available tools:
1. `search_schools`: Queries structured DB records.
2. `search_documents`: Performs vector search (RAG) over detailed PDF school guides.

CRITICAL RULES:
1. ALWAYS call `search_schools` first to get standard DB info.
2. If the user asks for COMPARISONS, DETAILS, RULES, ADVANTAGES, or ADMISSION PROCESS:
   - You MUST ALSO call `search_documents` for EACH school mentioned to get context from PDF guides.
3. NEVER assume missing values (e.g., guessing minimum score or industrial partner). If information is absent, state clearly that it is not available.
4. Combine results from both tools into a complete, accurate Arabic response.
"""

# =====================================================
# Agent State
# =====================================================

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]


# =====================================================
# Agent Node
# =====================================================

async def agent_node(state: AgentState) -> dict:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        *state["messages"],
    ]

    response = await llm_with_tools.ainvoke(messages)

    return {
        "messages": [response]
    }


# =====================================================
# Router
# =====================================================

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]

    if getattr(last_message, "tool_calls", None):
        return "tools"

    return "end"


# =====================================================
# Build Graph
# =====================================================

graph_builder = StateGraph(AgentState)

graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", ToolNode(tools))

graph_builder.set_entry_point("agent")

graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END,
    },
)

graph_builder.add_edge("tools", "agent")

agent_graph = graph_builder.compile()


# =====================================================
# Run Agent
# =====================================================

async def run_agent(question: str) -> dict[str, Any]:
    """
    Run the AI Agent.

    Returns:
    {
        "answer": "...",
        "steps": [
            {
                "tool": "...",
                "args": {...}
            }
        ]
    }
    """

    initial_state = {
        "messages": [
            HumanMessage(content=question)
        ]
    }

    result = await agent_graph.ainvoke(
        initial_state,
        config={
            "callbacks": [langfuse_handler],
        },
    )

    final_message = result["messages"][-1]

    steps = []

    for message in result["messages"]:
        if getattr(message, "tool_calls", None):
            for tool_call in message.tool_calls:
                steps.append(
                    {
                        "tool": tool_call["name"],
                        "args": tool_call["args"],
                    }
                )

    return {
        "answer": final_message.content,
        "steps": steps,
    }