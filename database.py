#database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./finance.db"

# Cria engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, echo=True)

# Base para os modelos
Base = declarative_base()

# Sessão
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Função para criar tabelas
def init_db():
    from models import Base
    Base.metadata.create_all(bind=engine)
    print("Tabelas criadas com sucesso!")

# Dependency FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
