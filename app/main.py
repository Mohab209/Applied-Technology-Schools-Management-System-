import os
from fastapi import FastAPI, HTTPException, status, Depends, Security, UploadFile, File
from fastapi.security.api_key import APIKeyHeader
from typing import List
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from app.database import get_db, engine, Base
from app.models import School
from app.schemas import SchoolCreate, SchoolUpdate, SchoolResponse, SchoolExtractionRequest, SchoolExtractionResponse, RAGQueryRequest, RAGQueryResponse, RAGIngestResponse, RAGSourceResponse, AgentRequest, AgentResponse
from app.llm_service import extract_school
from app.rag_service import answer_query, ingest_document, list_ingested_sources
from app.agent_service import run_agent

load_dotenv()

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API_KEY not set"
        )
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is missing. Add 'X-API-Key' header"
        )
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return api_key

app = FastAPI(title="Applied Technology Schools", version="1.0.0")

Base.metadata.create_all(bind=engine)

@app.get("/schools", response_model=List[SchoolResponse])
def get_all_schools(db: Session = Depends(get_db)):
    return db.query(School).all()

@app.get("/schools/{id}", response_model=SchoolResponse)
def get_school(id: int, db: Session = Depends(get_db)):
    school = db.query(School).filter(School.id == id).first()

    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    return school

@app.post("/schools", response_model=SchoolResponse, status_code=201, dependencies=[Depends(verify_api_key)])
def create_movie(payload: SchoolCreate, db: Session = Depends(get_db)):
    new_school = School(**payload.dict())
    db.add(new_school)
    db.commit()
    db.refresh(new_school)
    return new_school

@app.patch("/schools/{id}", response_model=SchoolResponse)
def update_school(id: int, school_data: SchoolUpdate, db: Session = Depends(get_db), _: None = Depends(verify_api_key),):
    school = db.query(School).filter(School.id == id).first()

    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    for key, value in school_data.model_dump(exclude_unset=True).items():
        setattr(school, key, value)

    db.commit()
    db.refresh(school)

    return school

@app.delete("/schools/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_school(
    id: int, 
    db: Session = Depends(get_db), 
    _: None = Depends(verify_api_key)
):
    school = db.query(School).filter(School.id == id).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    db.delete(school)
    db.commit()
    
    return None

@app.post("/llm/extract-school", response_model=SchoolResponse)
async def extract_school_endpoint(request: SchoolExtractionRequest, db: Session = Depends(get_db), _: None = Depends(verify_api_key),):
    school_data = await extract_school(text=request.text, provider=request.provider,)

    school = School(**school_data.model_dump())

    db.add(school)
    db.commit()
    db.refresh(school)

    return school

@app.post("/rag/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest, db: Session = Depends(get_db)):
    return await answer_query(
        query=request.question, 
        db=db, 
        school_id=request.school_id, 
        k=request.k
    )

from fastapi import UploadFile, File

@app.post("/rag/ingest", response_model=RAGIngestResponse)
async def ingest_pdf(
    school_id: int,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db), 
    _: None = Depends(verify_api_key)
):
    pdf_bytes = await file.read()

    chunks = await ingest_document(
        pdf_bytes=pdf_bytes,
        filename=file.filename,
        school_id=school_id,
        db=db
    )

    return {
        "message": f"Successfully ingested {file.filename!r} for school ID {school_id}", 
        "chunks": chunks
    }

@app.get("/rag/sources", response_model=List[RAGSourceResponse])
def get_sources(db: Session = Depends(get_db)):
    return list_ingested_sources(db)

@app.post(
    "/agent",
    response_model=AgentResponse,
    tags=["AI Agent"],
)
async def agent(request: AgentRequest):

    return await run_agent(request.question)