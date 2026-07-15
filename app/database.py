# Import Needed Libraries
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load Environmental variables from the .env file
load_dotenv()

# Get DATABSA_URL From .env
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Establish the connection engine
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Dependency to yield database sessions to our FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
