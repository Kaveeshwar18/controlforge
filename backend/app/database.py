import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# CONTROLFORGE_DB lets tests and the multi-seed experiment point at a
# throwaway database without touching the dev one.
DB_PATH = os.environ.get(
    "CONTROLFORGE_DB",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "coe_dashboard.sqlite3"),
)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
