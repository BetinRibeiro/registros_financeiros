# Dockerfile para FastAPI + PostgreSQL
FROM python:3.12-slim

# Diretório de trabalho dentro do container
WORKDIR /app

# Copia o requirements.txt
COPY requirements.txt .

# Instala dependências sem cache
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o restante do projeto para o container
COPY . .

# Porta que o FastAPI vai rodar
EXPOSE 8080

# Comando para rodar a aplicação
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
