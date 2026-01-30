#models.py
from sqlalchemy import String, Float, DateTime, Boolean, ForeignKey, Date
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from datetime import datetime
import uuid

# ------------------ ACESSO ------------------
class Acesso(Base):
    __tablename__ = "acessos"
    id: Mapped[uuid.UUID] = mapped_column(BLOB, primary_key=True, default=uuid.uuid4)
    cpf: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    registros: Mapped[list] = relationship("RegistroFinanceiro", back_populates="acesso")

# ------------------ REGISTRO FINANCEIRO ------------------
class RegistroFinanceiro(Base):
    __tablename__ = "registros_financeiros"
    id: Mapped[uuid.UUID] = mapped_column(BLOB, primary_key=True, default=uuid.uuid4)
    acesso_id: Mapped[uuid.UUID] = mapped_column(BLOB, ForeignKey("acessos.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)  # entrada ou saida
    categoria: Mapped[str] = mapped_column(String, nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    forma_pagamento: Mapped[str] = mapped_column(String, nullable=False)
    descricao: Mapped[str] = mapped_column(String, default="")
    data_vencimento: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    data_liquidacao: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pendente")
    observacao: Mapped[str] = mapped_column(String, default="")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    acesso: Mapped[Acesso] = relationship("Acesso", back_populates="registros")
