# app/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from sqlalchemy.sql import func
from app.database import Base


class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    arabic_name = Column(String(200), nullable=False)
    english_name = Column(String(200), nullable=True)
    established_year = Column(Integer, nullable=False)
    specialization = Column(String(50), nullable=False)
    location = Column(String(100), nullable=False)
    accepted_governorates = Column(String(200),nullable=False,default="All")
    minimum_score = Column(Integer, nullable=False)
    industrial_partner = Column(String(100), nullable=True)
    study_duration = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    official_website = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime,server_default=func.now(),onupdate=func.now())
    is_active = Column(Boolean, nullable=False, default=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    doc_metadata = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        source = (self.doc_metadata or {}).get("source", "unkown")
        return f"<Document id={self.id} source={source!r} content={self.content[:40]!r}...>"