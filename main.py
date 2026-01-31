from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import re
import time

# 🔹 Importa o engine e a Base do database
from database import get_db, engine, Base

# 🔹 Importa APENAS os models
import models
from models import Acesso, RegistroFinanceiro

# 🔹 Cria a aplicação
app = FastAPI(title="API Financeira")

# ------------------ CORS ------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ RATE LIMIT ------------------
RATE_LIMIT = 30  # requisições
TIME_WINDOW = 60  # segundos
rate_limit_store = {}  # ip -> [timestamps]

def rate_limiter(request: Request):
    ip = request.client.host
    now = time.time()
    timestamps = rate_limit_store.get(ip, [])
    timestamps = [t for t in timestamps if now - t < TIME_WINDOW]
    if len(timestamps) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Muitas requisições, tente novamente mais tarde")
    timestamps.append(now)
    rate_limit_store[ip] = timestamps

# ------------------ MODELS ------------------
class AcessoOut(BaseModel):
    id: UUID
    cpf: str
    class Config:
        from_attributes = True

class RegistroFinanceiroCreate(BaseModel):
    tipo: str
    categoria: str
    valor: float
    forma_pagamento: str
    descricao: Optional[str] = ""
    data_vencimento: datetime
    data_liquidacao: Optional[datetime] = None
    status: str
    observacao: Optional[str] = ""

class RegistroFinanceiroUpdate(BaseModel):
    tipo: Optional[str]
    categoria: Optional[str]
    valor: Optional[float]
    forma_pagamento: Optional[str]
    descricao: Optional[str]
    data_vencimento: Optional[datetime]
    data_liquidacao: Optional[datetime]
    status: Optional[str]
    observacao: Optional[str]

class RegistroFinanceiroOut(BaseModel):
    id: UUID
    acesso_id: UUID
    tipo: str
    categoria: str
    valor: float
    forma_pagamento: str
    descricao: str
    data_vencimento: datetime
    data_liquidacao: Optional[datetime]
    status: str
    observacao: str
    ativo: bool
    created_at: datetime
    updated_at: datetime
    class Config:
        orm_mode = True

# ------------------ FUNÇÕES AUXILIARES ------------------
def aplicar_offset_limit(query, offset: int, limit: int):
    if limit > 100:
        limit = 100
    return query.offset(offset).limit(limit), limit

def set_pagination_headers(response: Response, total: int, offset: int, limit: int, acesso_id: str):
    response.headers["X-Total"] = str(total)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Acesso-ID"] = acesso_id
    response.headers["Access-Control-Expose-Headers"] = "X-Total, X-Offset, X-Limit, X-Acesso-ID"

def validar_cpf(cpf: str) -> bool:
    cpf_numeros = re.sub(r"\D", "", cpf)
    if len(cpf_numeros) != 11:
        return False
    if cpf_numeros == cpf_numeros[0] * 11:
        return False
    soma1 = sum(int(cpf_numeros[i]) * (10 - i) for i in range(9))
    digito1 = (soma1 * 10 % 11) % 10
    soma2 = sum(int(cpf_numeros[i]) * (11 - i) for i in range(10))
    digito2 = (soma2 * 10 % 11) % 10
    return digito1 == int(cpf_numeros[9]) and digito2 == int(cpf_numeros[10])

# ------------------ STARTUP ------------------
async def criar_tabelas():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    await criar_tabelas()

# ------------------ ENDPOINT ACESSO ------------------
@app.post("/acesso", response_model=AcessoOut)
async def get_or_create_acesso(cpf: str, db: AsyncSession = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    cpf_numeros = re.sub(r"\D", "", cpf)
    if not validar_cpf(cpf_numeros):
        raise HTTPException(status_code=400, detail="CPF inválido.")
    result = await db.execute(select(Acesso).where(Acesso.cpf == cpf_numeros))
    acesso = result.scalar_one_or_none()
    if acesso:
        return acesso
    novo = Acesso(cpf=cpf_numeros)
    db.add(novo)
    await db.commit()
    await db.refresh(novo)
    return novo

@app.get("/acessos", response_model=List[AcessoOut])
async def listar_acessos(response: Response, offset: int = 0, limit: int = 10,
                         db: AsyncSession = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    result = await db.execute(select(Acesso))
    query = result.scalars()
    total = await db.execute(select(Acesso))
    total_count = len(total.scalars().all())
    # Offset e limit manual
    query_list = query.all()[offset:offset+limit]
    set_pagination_headers(response, total_count, offset, limit, acesso_id="")
    return query_list

# ------------------ REGISTROS FINANCEIROS ------------------
@app.get("/registros", response_model=List[RegistroFinanceiroOut])
async def listar_registros(
    acesso_id: str,
    response: Response,
    offset: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    if request:
        rate_limiter(request)
    result = await db.execute(
        select(RegistroFinanceiro)
        .where(RegistroFinanceiro.acesso_id == str(acesso_id))
        .where(RegistroFinanceiro.ativo == True)
    )
    registros = result.scalars().all()
    total = len(registros)
    registros_pag = registros[offset:offset+limit]
    set_pagination_headers(response, total, offset, limit, acesso_id)
    return registros_pag

@app.post("/registros", response_model=RegistroFinanceiroOut)
async def criar_registro(acesso_id: str, registro: RegistroFinanceiroCreate,
                         db: AsyncSession = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    result = await db.execute(select(Acesso).where(Acesso.id == acesso_id))
    acesso = result.scalar_one_or_none()
    if not acesso:
        raise HTTPException(status_code=404, detail="Acesso não encontrado")
    novo_registro = RegistroFinanceiro(acesso_id=acesso_id, **registro.dict())
    try:
        db.add(novo_registro)
        await db.commit()
        await db.refresh(novo_registro)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar registro: {str(e)}")
    return novo_registro

@app.put("/registros/{registro_id}", response_model=RegistroFinanceiroOut)
async def alterar_registro(registro_id: UUID, registro_update: RegistroFinanceiroUpdate,
                           db: AsyncSession = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    result = await db.execute(
        select(RegistroFinanceiro)
        .where(RegistroFinanceiro.id == str(registro_id))
        .where(RegistroFinanceiro.ativo == True)
    )
    registro = result.scalar_one_or_none()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    for key, value in registro_update.dict(exclude_unset=True).items():
        setattr(registro, key, value)
    registro.updated_at = datetime.utcnow()
    try:
        await db.commit()
        await db.refresh(registro)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar registro: {str(e)}")
    return registro

@app.delete("/registros/{registro_id}", response_model=dict)
async def deletar_registro(registro_id: UUID, db: AsyncSession = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    result = await db.execute(
        select(RegistroFinanceiro)
        .where(RegistroFinanceiro.id == str(registro_id))
        .where(RegistroFinanceiro.ativo == True)
    )
    registro = result.scalar_one_or_none()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    registro.ativo = False
    registro.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "detail": f"Registro {registro_id} desativado com sucesso",
        "id": registro.id,
        "ativo": registro.ativo,
        "updated_at": registro.updated_at.isoformat()
    }
