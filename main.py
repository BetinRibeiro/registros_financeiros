from fastapi import FastAPI, HTTPException, Depends, Response, Request
from sqlalchemy.orm import Session
from models import Acesso, RegistroFinanceiro
from database import init_db, get_db
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import time

# ------------------ INIT ------------------
init_db()
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
        orm_mode = True

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

# ------------------ FUNÇÕES AUX ------------------
def aplicar_offset_limit(query, offset: int, limit: int):
    if limit > 100:
        limit = 100
    return query.offset(offset).limit(limit), limit

def set_pagination_headers(response: Response, total: int, offset: int, limit: int, acesso_id: UUID):
    response.headers["X-Total"] = str(total)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Acesso-ID"] = str(acesso_id or "-")

# ------------------ ENDPOINT ACESSO ------------------
@app.post("/acesso", response_model=AcessoOut)
def get_or_create_acesso(cpf: str, db: Session = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    acesso = db.query(Acesso).filter(Acesso.cpf == cpf).first()
    if acesso:
        return acesso
    novo = Acesso(cpf=cpf)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

# ------------------ CRUD REGISTRO FINANCEIRO ------------------
@app.get("/registros", response_model=List[RegistroFinanceiroOut])
def listar_registros(acesso_id: UUID, offset: int = 0, limit: int = 10,
                    response: Response = None, db: Session = Depends(get_db),
                    request: Request = None):
    if request:
        rate_limiter(request)
    query = db.query(RegistroFinanceiro).filter(RegistroFinanceiro.acesso_id == acesso_id, RegistroFinanceiro.ativo==True)
    total = query.count()
    query, limit = aplicar_offset_limit(query, offset, limit)
    set_pagination_headers(response, total, offset, limit, acesso_id)
    return query.all()

@app.post("/registros", response_model=RegistroFinanceiroOut)
def criar_registro(acesso_id: UUID, registro: RegistroFinanceiroCreate,
                   db: Session = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    novo = RegistroFinanceiro(acesso_id=acesso_id, **registro.dict())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.put("/registros/{registro_id}", response_model=RegistroFinanceiroOut)
def alterar_registro(registro_id: UUID, registro_update: RegistroFinanceiroUpdate,
                     db: Session = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    registro = db.query(RegistroFinanceiro).filter(RegistroFinanceiro.id==registro_id, RegistroFinanceiro.ativo==True).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    for key, value in registro_update.dict(exclude_unset=True).items():
        setattr(registro, key, value)
    registro.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(registro)
    return registro

@app.delete("/registros/{registro_id}")
def deletar_registro(registro_id: UUID, db: Session = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)
    registro = db.query(RegistroFinanceiro).filter(RegistroFinanceiro.id==registro_id, RegistroFinanceiro.ativo==True).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    registro.ativo = False
    registro.updated_at = datetime.utcnow()
    db.commit()
    return {"detail": f"Registro {registro_id} desativado"}
