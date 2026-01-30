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
import re

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
    
def set_pagination_headers(response: Response, total: int, offset: int, limit: int, acesso_id: str):
    response.headers["X-Total"] = str(total)
    response.headers["X-Offset"] = str(offset)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Acesso-ID"] = acesso_id


# ------------------ VALIDA CPF ------------------#

def validar_cpf(cpf: str) -> bool:
    """
    Valida um CPF verificando os dígitos verificadores.
    Retorna True se for válido, False caso contrário.
    """

    # Remove tudo que não for número
    cpf_numeros = re.sub(r"\D", "", cpf)

    # Deve ter 11 dígitos
    if len(cpf_numeros) != 11:
        return False

    # CPF não pode ter todos os números iguais (ex: 11111111111)
    if cpf_numeros == cpf_numeros[0] * 11:
        return False

    # --------------------------
    # Calcula o primeiro dígito verificador
    # --------------------------
    soma1 = sum(int(cpf_numeros[i]) * (10 - i) for i in range(9))
    digito1 = (soma1 * 10 % 11) % 10

    # --------------------------
    # Calcula o segundo dígito verificador
    # --------------------------
    soma2 = sum(int(cpf_numeros[i]) * (11 - i) for i in range(10))
    digito2 = (soma2 * 10 % 11) % 10

    # Compara com os dígitos do CPF
    return digito1 == int(cpf_numeros[9]) and digito2 == int(cpf_numeros[10])



# ------------------ ENDPOINT ACESSO ------------------
@app.post("/acesso", response_model=AcessoOut)
def get_or_create_acesso(cpf: str, db: Session = Depends(get_db), request: Request = None):
    if request:
        rate_limiter(request)

    # 1️⃣ Limpa CPF: remove tudo que não for número
    cpf_numeros = re.sub(r"\D", "", cpf)

    # 2️⃣ Valida CPF usando função validar_cpf
    if not validar_cpf(cpf_numeros):
        raise HTTPException(status_code=400, detail="CPF inválido.")

    # 3️⃣ Consulta se já existe
    acesso = db.query(Acesso).filter(Acesso.cpf == cpf_numeros).first()
    if acesso:
        return acesso

    # 4️⃣ Se não existir, cria novo registro
    novo = Acesso(cpf=cpf_numeros)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo

@app.get("/acessos", response_model=List[AcessoOut])
def listar_acessos(
    offset: int = 0,
    limit: int = 10,
    response: Response,  # <- sem =None, FastAPI injeta
    db: Session = Depends(get_db),
    request: Request = None
):
    if request:
        rate_limiter(request)

    # Query de acessos
    query = db.query(Acesso)
    total = query.count()

    # aplica offset e limit
    query, limit = aplicar_offset_limit(query, offset, limit)

    # adiciona headers de paginação
    set_pagination_headers(response, total, offset, limit, acesso_id="")  # Aqui pode passar "" ou None se não houver filtro

    # retorna registros
    return query.all()




# ------------------ FUNÇÕES AUXILIARES ------------------
def aplicar_offset_limit(query, offset: int, limit: int):
    """
    Aplica offset e limit em uma query SQLAlchemy.
    Limita máximo de registros por página a 100.
    """
    if limit > 100:
        limit = 100
    return query.offset(offset).limit(limit), limit

# ------------------ LISTAR REGISTROS FINANCEIROS ------------------
@app.get("/registros", response_model=List[RegistroFinanceiroOut])
def listar_registros(
    acesso_id: str, 
    offset: int = 0, 
    limit: int = 10,
    response: Response = None, 
    db: Session = Depends(get_db),
    request: Request = None
):
    """
    Lista os registros financeiros de um acesso específico.
    Retorna lista de registros ativos com cabeçalhos de paginação.
    Headers adicionados:
        X-Total -> total de registros
        X-Offset -> offset usado
        X-Limit -> limite usado
        X-Acesso-ID -> ID do acesso filtrado
    """
    if request:
        rate_limiter(request)

    # Query filtrando apenas registros ativos do acesso_id
    query = db.query(RegistroFinanceiro).filter(
        RegistroFinanceiro.acesso_id == str(acesso_id),
        RegistroFinanceiro.ativo == True
    )

    # Total de registros
    total = query.count()

    # Aplica offset e limit
    query, limit = aplicar_offset_limit(query, offset, limit)

    # Adiciona cabeçalhos
    set_pagination_headers(response, total, offset, limit, acesso_id)

    # Retorna registros
    return query.all()



@app.post("/registros", response_model=RegistroFinanceiroOut)
def criar_registro(
    acesso_id: str,
    registro: RegistroFinanceiroCreate,
    db: Session = Depends(get_db),
    request: Request = None
):
    # ----------------- RATE LIMIT -----------------
    if request:
        rate_limiter(request)

    # ----------------- CHECAR ACESSO -----------------
    acesso = db.query(Acesso).filter(Acesso.id == acesso_id).first()
    if not acesso:
        raise HTTPException(status_code=404, detail="Acesso não encontrado")

    # ----------------- CRIAR REGISTRO -----------------
    novo_registro = RegistroFinanceiro(acesso_id=acesso_id, **registro.dict())

    try:
        db.add(novo_registro)
        db.commit()
        db.refresh(novo_registro)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar registro: {str(e)}")

    return novo_registro


@app.put("/registros/{registro_id}", response_model=RegistroFinanceiroOut)
def alterar_registro(
    registro_id: UUID,
    registro_update: RegistroFinanceiroUpdate,
    db: Session = Depends(get_db),
    request: Request = None
):
    # ----------------- RATE LIMIT -----------------
    if request:
        rate_limiter(request)

    # ----------------- BUSCAR REGISTRO -----------------
    registro = db.query(RegistroFinanceiro).filter(
        RegistroFinanceiro.id == str(registro_id),  # garantindo que compara strings
        RegistroFinanceiro.ativo == True
    ).first()

    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")

    # ----------------- ATUALIZAR CAMPOS -----------------
    # Só atualiza os campos que foram enviados no JSON
    for key, value in registro_update.dict(exclude_unset=True).items():
        setattr(registro, key, value)

    registro.updated_at = datetime.utcnow()  # atualizar timestamp

    # ----------------- COMMIT COM TRATAMENTO -----------------
    try:
        db.commit()
        db.refresh(registro)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar registro: {str(e)}")

    return registro


@app.delete("/registros/{registro_id}", response_model=dict)
def deletar_registro(registro_id: UUID, db: Session = Depends(get_db), request: Request = None):
    """
    Desativa um registro financeiro no banco de dados.
    
    Parâmetros:
    - registro_id: UUID do registro a ser desativado.
    - db: Sessão do SQLAlchemy (injetada via Depends).
    - request: Request do FastAPI (usado para limitar taxa de requisições).
    
    Fluxo:
    1. Aplica rate limiting se a requisição for recebida.
    2. Busca o registro pelo ID e somente se estiver ativo.
    3. Se não encontrado, retorna HTTP 404.
    4. Marca o registro como inativo (`ativo = False`) e atualiza o timestamp.
    5. Commit no banco e retorna confirmação.
    """
    
    # ------------------ RATE LIMIT ------------------
    if request:
        rate_limiter(request)

    # ------------------ BUSCA REGISTRO ------------------
    registro = db.query(RegistroFinanceiro)\
                 .filter(RegistroFinanceiro.id == str(registro_id),
                         RegistroFinanceiro.ativo == True)\
                 .first()
    
    # ------------------ VALIDAÇÃO ------------------
    if not registro:
        # Retorna 404 se o registro não existir ou já estiver desativado
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    
    # ------------------ DESATIVA REGISTRO ------------------
    registro.ativo = False
    registro.updated_at = datetime.utcnow()  # atualiza timestamp
    db.commit()  # salva alterações no banco

    # ------------------ RETORNO ------------------
    return {
        "detail": f"Registro {registro_id} desativado com sucesso",
        "id": registro.id,
        "ativo": registro.ativo,
        "updated_at": registro.updated_at.isoformat()
    }
