import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_PUBLIC_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_PUBLIC_URL não encontrada")

# 🔹 Substitui psycopg2 por psycopg3
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()





# antes era assim:

# # Importa a função create_engine, responsável por criar a conexão com o banco de dados
# from sqlalchemy import create_engine

# # Importa utilitários do SQLAlchemy:
# # - sessionmaker: cria sessões de conexão com o banco
# # - declarative_base: base para os modelos ORM
# from sqlalchemy.orm import sessionmaker, declarative_base

# # String de conexão com o banco SQLite
# # "sqlite:///" indica um banco local no mesmo diretório do projeto
# DATABASE_URL = "sqlite:///finance.db"  # note os 4 /

# # Cria o engine (motor de conexão) com o banco de dados
# # check_same_thread=False permite múltiplas threads acessarem o SQLite
# # echo=True faz o SQLAlchemy imprimir no terminal todas as queries SQL executadas
# engine = create_engine(
#     DATABASE_URL,
#     connect_args={"check_same_thread": False},
#     echo=True
# )

# # Cria a classe base que será herdada por todos os modelos (tabelas)
# Base = declarative_base()

# # Cria uma fábrica de sessões do banco de dados
# # autoflush=False evita envio automático de dados antes do commit
# # autocommit=False exige commit manual para salvar alterações
# SessionLocal = sessionmaker(
#     bind=engine,
#     autoflush=False,
#     autocommit=False
# )

# # Função responsável por criar todas as tabelas no banco de dados
# def init_db():
#     # Importa a Base dos models para registrar todas as tabelas
#     # Esse import garante que todos os modelos sejam carregados
#     from models import Base

#     # Cria todas as tabelas definidas nos modelos no banco de dados
#     Base.metadata.create_all(bind=engine)

#     # Mensagem de confirmação no terminal
#     print("Tabelas criadas com sucesso!")

# # Função geradora que fornece uma sessão do banco para uso na API
# # Muito usada com Depends(get_db) no FastAPI
# def get_db():
#     # Cria uma nova sessão do banco
#     db = SessionLocal()
#     try:
#         # Retorna a sessão para quem chamou a função
#         yield db
#     finally:
#         # Garante que a sessão será fechada após o uso
#         db.close()

# # Verifica se este arquivo está sendo executado diretamente
# # (e não importado por outro arquivo)
# if __name__ == "__main__":
#     # Executa a criação das tabelas ao rodar o arquivo diretamente
#     init_db()
