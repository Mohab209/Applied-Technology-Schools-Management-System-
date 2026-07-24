import os
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
from sqlalchemy import select, or_
from langfuse.langchain import CallbackHandler

from app.database import SessionLocal
from app.models import School
from app.rag_service import answer_query as rag_answer_query

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
def search_schools(
    names: list[str] | None = None,
    specialization: str | None = None,
    location: str | None = None,
    industrial_partner: str | None = None,
    minimum_score: int | None = None,
) -> list[dict]:
    """
    Search schools stored in the database.

    Use this tool whenever the user asks about:
    - schools
    - locations
    - specializations
    - industrial partners
    - minimum score
    - comparisons between schools
    """

    db = SessionLocal()

    try:

        stmt = select(School)

        if names:

            conditions = []

            for name in names:

                conditions.append(
                    School.arabic_name.ilike(f"%{name}%")
                )

                conditions.append(
                    School.english_name.ilike(f"%{name}%")
                )

            stmt = stmt.where(or_(*conditions))

        if specialization:

            stmt = stmt.where(
                School.specialization.ilike(
                    f"%{specialization}%"
                )
            )

        if location:

            stmt = stmt.where(
                School.location.ilike(
                    f"%{location}%"
                )
            )

        if industrial_partner:

            stmt = stmt.where(
                School.industrial_partner.ilike(
                    f"%{industrial_partner}%"
                )
            )

        if minimum_score is not None:

            stmt = stmt.where(
                School.minimum_score >= minimum_score
            )

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
async def search_documents(question: str) -> str:
    """
    Search the uploaded PDF documents using RAG.

    Use this tool whenever the answer should come
    from the uploaded PDF files.
    """

    db = SessionLocal()

    try:

        result = await rag_answer_query(
            query=question,
            db=db,
            k=3,
        )

        return result["answer"]

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
You are an AI Assistant for the Applied Technology Schools Management System.

Your goal is to answer questions about Applied Technology Schools in Egypt.

Available tools:

1. search_schools

Use this tool for:
- school information
- comparing schools
- locations
- specializations
- industrial partners
- minimum score
- study duration
- accepted governorates
- official website

2. search_documents

Use this tool whenever the answer requires searching
the uploaded PDF documents.

Guidelines:

- Always use tools before answering.
- Never make up information.
- If search_schools contains enough information,
  do not call search_documents.
- If database information is insufficient,
  use search_documents.
- You may call both tools if needed.
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

graph_builder.add_node(
    "agent",
    agent_node,
)

graph_builder.add_node(
    "tools",
    ToolNode(tools),
)

graph_builder.set_entry_point("agent")

graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "end": END,
    },
)

graph_builder.add_edge(
    "tools",
    "agent",
)

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