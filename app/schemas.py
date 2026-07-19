from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class SchoolBase(BaseModel):
    arabic_name: str = Field(..., min_length=5, max_length=200)
    english_name: Optional[str] = Field(None, min_length=5, max_length=200)
    established_year: int = Field(..., ge=2015, le=2030)
    specialization: str = Field(..., min_length=2, max_length=200)
    location: str = Field(..., min_length=2, max_length=100)
    accepted_governorates: str = Field(default="All", max_length=200)
    minimum_score: int = Field(..., ge=140, le=280)
    industrial_partner: Optional[str] = Field(None, min_length=2, max_length=200)
    study_duration: int = Field(..., ge=3, le=5)
    description: Optional[str] = Field(None, max_length=1000)
    official_website: Optional[str] = Field(None, max_length=255)

class SchoolCreate(SchoolBase):
    pass

class SchoolUpdate(BaseModel):
    arabic_name: Optional[str] = Field(None, min_length=5, max_length=200)
    english_name: Optional[str] = Field(None, min_length=5, max_length=200)
    established_year: Optional[int] = Field(None, ge=2015, le=2030)
    specialization: Optional[str] = Field(None, min_length=2, max_length=200)
    location: Optional[str] = Field(None, min_length=2, max_length=100)
    accepted_governorates: Optional[str] = Field(None, max_length=200)
    minimum_score: Optional[int] = Field(None, ge=140, le=280)
    industrial_partner: Optional[str] = Field(None, min_length=2, max_length=200)
    study_duration: Optional[int] = Field(None, ge=3, le=5)
    description: Optional[str] = Field(None, max_length=1000)
    official_website: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None

class SchoolResponse(SchoolBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class SchoolExtractionRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10000)
    provider: Literal["groq", "hf"] = "groq"

class SchoolExtractionResponse(SchoolBase):
    pass

class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="The user's question")
    school_id: int = Field(..., description="The ID of the school to query within")
    k: int = Field(6, ge=1, le=20, description="Number of chunks to retrieve")

class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[dict]

class RAGIngestResponse(BaseModel):
    message: str
    chunks: int

class RAGSourceResponse(BaseModel):
    source: str
    chunk_count: int
    last_ingested: Optional[str] = None