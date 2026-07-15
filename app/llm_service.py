import os
import json
import asyncio
from openai import AsyncOpenAI, APITimeoutError, RateLimitError, APIConnectionError
from dotenv import load_dotenv
from app.schemas import SchoolExtractionResponse

load_dotenv()

PROVIDERS = {
    "groq": {
        "client": AsyncOpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        ),
        "model": "llama-3.3-70b-versatile",
    },
    "hf": {
        "client": AsyncOpenAI(
            api_key=os.getenv("HF_TOKEN"),
            base_url="https://router.huggingface.co/v1",
        ),
        "model": "openai/gpt-oss-120b:cerebras",
    }
}

RETRYABLE_ERROR = (APITimeoutError, RateLimitError, APIConnectionError)
MAX_ATTEMPTS = 3
BASE_DELAY_SECONDS = 1.0
TIMEOUT_SECONDS = 20.0

async def _call_llm_with_retry(
    client: AsyncOpenAI,
    model: str,
    messages: list,
) -> str:
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                timeout=TIMEOUT_SECONDS,
            )
            return response.choices[0].message.content

        except RETRYABLE_ERROR as e:
            last_error = e
            if attempt == MAX_ATTEMPTS:
                raise
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            print(f"[llm_service] Attempt{attempt} failed ({type(e).__name__}). Retrying in {delay}s.")
            await asyncio.sleep(delay)
    raise last_error

SYSTEM_PROMPT = """
You are an expert at extracting structured information about Applied Technology Schools in Egypt.

Extract the following JSON fields:

- arabic_name
- english_name
- established_year
- specialization
- location
- accepted_governorates
- minimum_score
- industrial_partner
- study_duration
- description
- official_website

Rules:

1. Return VALID JSON only.
2. Never return markdown.
3. Never return explanations.
4. Never return empty strings.
5. Never invent information.
6. official_website may be null.
7. accepted_governorates:
   - If not explicitly mentioned, return "All".
8. english_name:
   - Always generate it from the Arabic name if it isn't written.
9. description:
   - Generate a short factual description using ONLY the provided text.

IMPORTANT

The following fields are REQUIRED:

- arabic_name
- established_year
- specialization
- location
- minimum_score
- industrial_partner
- study_duration

If ANY of them cannot be determined from the text,
DO NOT GUESS.

Instead return ONLY:

{
  "error":"Missing required information",
  "missing_fields":[
    "field_name"
  ]
}

Never return partial data.

Some schools have multiple branches.

Treat every branch as a completely different school.

Examples:
WE School Badr
WE School Alexandria
WE School Assiut

are three different schools.

Never merge branches.
"""

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "مدرسة ابدأ الوطنية للعلوم التقنية ببدر محافظة القاهرة متخصصة في الذكاء الاصطناعي وتحليل البيانات افتتحت سنة 2023 بالشراكة مع مبادرة ابدأ الرئاسية وشركة تأهيل ومؤسسة أمنيا الفنلندية وتقبل من القاهرة والقليوبية والشرقية والسويس والجيزة والحد الأدنى 240."
    },
    {
        "role": "assistant",
        "content": """
{
  "arabic_name":"مدرسة ابدأ الوطنية للعلوم التقنية",
  "english_name":"Ebda National School for Technical Sciences",
  "established_year":2023,
  "specialization":"Artificial Intelligence and Data Analysis",
  "location":"Badr, Cairo",
  "accepted_governorates":"Cairo, Qalyubia, Sharqia, Suez, Giza",
  "minimum_score":240,
  "industrial_partner":"Ebda Presidential Initiative, Taheel, Omnia Finland",
  "study_duration":3,
  "description":"Applied Technology School specializing in Artificial Intelligence and Data Analysis located in Badr City.",
  "official_website":null
}
"""
    },

    {
        "role":"user",
        "content":"مدرسة WE للتكنولوجيا التطبيقية بمدينة نصر متخصصة في الاتصالات وتكنولوجيا المعلومات والحد الأدنى 250 بالشراكة مع المصرية للاتصالات."
    },
    {
        "role":"assistant",
        "content":"""
{
  "error":"Missing required information",
  "missing_fields":[
    "established_year"
  ]
}
"""
    }
]

async def extract_school(text: str, provider: str = "groq") -> SchoolExtractionResponse:
    if provider not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {provider!r}. "
            f"Choose from: {list(PROVIDERS.keys())}"
        )

    config = PROVIDERS[provider]

    response = await _call_llm_with_retry(
        client=config["client"],
        model=config["model"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            *FEW_SHOT_EXAMPLES,
            {"role": "user", "content": text},
        ],
    )
    print(response)
    data = json.loads(response)

    if "error" in data:
        raise ValueError(
            f"{data['error']}: {', '.join(data['missing_fields'])}"
        )

    return SchoolExtractionResponse(**data)