# 🎓 Applied Technology Schools Management & Smart RAG System

A production-ready **Full-Stack AI-powered Web Application** for managing, searching, and extracting information about Egypt's **Applied Technology Schools**.

The platform combines **FastAPI**, **PostgreSQL**, **Vector Search (pgvector)**, **Large Language Models (LLMs)**, and **Retrieval-Augmented Generation (RAG)** to automate school data management and provide an intelligent document-based assistant.

---

# 📖 Overview

Applied Technology Schools are becoming one of Egypt's most important educational initiatives. Unfortunately, information about these schools is scattered across Facebook posts, ministry announcements, PDF guides, and news articles.

This project centralizes all school information into a structured database while leveraging Generative AI to automate data extraction and answer questions directly from official documents.

---

# 🎯 Problem

Students usually struggle to find information such as:

- Admission requirements
- Minimum accepted score
- Specializations
- Industrial partners
- School locations
- Accepted governorates
- Available accommodation
- Transportation
- Study duration
- Career opportunities

The information exists, but it is spread across lengthy documents and social media announcements.

Manual data entry is also repetitive and error-prone.

---

# 💡 Solution

The system provides two AI-powered services.

## 1. AI Data Extraction

Administrators can paste any Arabic text describing a school.

Example sources:

- Facebook posts
- Ministry announcements
- News articles
- Official websites

The LLM extracts structured information such as:

- Arabic Name
- English Name
- Location
- Specialization
- Minimum Score
- Industrial Partner
- Description
- Website
- Establishment Year

The extracted data is validated using Pydantic and stored automatically in PostgreSQL.

---

## 2. Smart PDF Question Answering (RAG)

Administrators upload official PDF documents.

The backend:

- Extracts text
- Splits documents into chunks
- Generates embeddings
- Stores vectors inside PostgreSQL using pgvector

When users ask questions, the system:

1. Converts the question into an embedding.
2. Searches the vector database.
3. Retrieves the most relevant chunks.
4. Sends them to the LLM.
5. Returns an answer grounded only in the uploaded documents.

This prevents hallucinations and produces reliable answers.

---

# 🏗️ System Architecture

```text
                    +----------------------+
                    |   Streamlit Frontend |
                    +----------+-----------+
                               |
                               | REST API
                               |
                               v
                    +----------------------+
                    |    FastAPI Backend   |
                    +----------+-----------+
                               |
          +--------------------+--------------------+
          |                                         |
          v                                         v
 +----------------------+               +----------------------+
 | PostgreSQL + pgvector|               | Groq / HuggingFace   |
 | Schools & Vectors    |               | LLM & Embeddings     |
 +----------------------+               +----------------------+
```

---

# ⚙️ Backend Workflow

## CRUD Operations

- Create Schools
- Read Schools
- Update Schools
- Delete Schools

---

## LLM Extraction Pipeline

```
Arabic Text
      │
      ▼
Prompt Engineering
      │
      ▼
Groq / HuggingFace
      │
      ▼
Structured JSON
      │
      ▼
Pydantic Validation
      │
      ▼
PostgreSQL
```

---

## RAG Pipeline

```
PDF
 │
 ▼
Extract Text
 │
 ▼
Chunk Document
 │
 ▼
Generate Embeddings
 │
 ▼
Store in pgvector
 │
 ▼
User Question
 │
 ▼
Similarity Search
 │
 ▼
Top-K Chunks
 │
 ▼
LLM
 │
 ▼
Grounded Answer
```

---

# ✨ Features

## School Management

- Full CRUD API
- PostgreSQL database
- SQLAlchemy ORM
- Pydantic validation

## AI Features

- Arabic school information extraction
- Multiple LLM providers
- Provider switching (Groq / HuggingFace)
- Prompt engineering
- Strict JSON validation

## RAG Features

- PDF ingestion
- Automatic chunking
- Embedding generation
- Semantic vector search
- Context-aware answers
- Source citation
- pgvector integration

## Security

- API Key Authentication
- Protected admin endpoints
- Request validation

## Frontend

- Streamlit Dashboard
- RTL Arabic support
- Interactive forms
- File upload interface
- AI Playground
- RAG Chat Interface

---

# 🛠️ Tech Stack

## Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- pgvector
- Pydantic

## AI

- Groq API
- Hugging Face Inference API
- LangChain
- Llama 3

## Frontend

- Streamlit

## Deployment

- Railway
- Streamlit Community Cloud
- Docker

---

# 📂 Project Structure

```text
Applied-Technology-Schools/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── llm_service.py
│   └── rag_service.py
│
├── frontend/
│   └── app_frontend.py
│
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

# ⚙️ Environment Variables

## Backend (.env)

```env
DATABASE_URL=postgresql://<username>:<password>@<host>:<port>/<database>

API_KEY=your_super_secret_admin_api_key

GROQ_API_KEY=your_groq_api_key

HF_TOKEN=your_huggingface_token
```

---

## Frontend (Streamlit Secrets)

Configure the following secrets in **Streamlit Community Cloud**.

```toml
API_BASE_URL="YOUR API_BASE_URL"

API_KEY="your_super_secret_admin_api_key"
```

---

# 🚀 Local Installation

## Clone Repository

```bash
git clone https://github.com/your-username/Applied-Technology-Schools.git

cd Applied-Technology-Schools
```

---

## Create Virtual Environment

Windows

```bash
python -m venv venv

venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv venv

source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment Variables

Create a `.env` file in the project root.

---

## Run FastAPI

```bash
uvicorn app.main:app --reload
```

Swagger UI

```
http://127.0.0.1:8000/docs
```

---

## Run Streamlit

```bash
streamlit run frontend/streamlit_app.py
```

---

# ☁️ Deployment

## Backend (Railway)

Deploy only the FastAPI backend.

Required environment variables:

```
DATABASE_URL
API_KEY
GROQ_API_KEY
HF_TOKEN
```

Railway automatically provides a public URL similar to:

```
https://your-backend.up.railway.app
```

---

## Frontend (Streamlit Community Cloud)

Deploy

```
frontend/streamlit_app.py
```

Configure Secrets:

```toml
API_BASE_URL="YOUR API_BASE_URL"

API_KEY="YOUR API KEY"
```

The frontend communicates with the Railway-hosted FastAPI backend through REST APIs.

---

# 🐳 Docker

Build

```bash
docker build -t applied-technology-api .
```

Run

```bash
docker run -p 8000:8000 --env-file .env applied-technology-api
```

---

# 📚 API Documentation

After starting the backend:

Swagger UI

```
http://127.0.0.1:8000/docs
```

ReDoc

```
http://127.0.0.1:8000/redoc
```

---

# 👨‍💻 Developed By

**Mohab Ahmed**

Data Analyst | AI & Data Analysis Student

GitHub

https://github.com/Mohab209

LinkedIn

https://www.linkedin.com/in/mohabhigazy