# Escolhe a imagem do Python com Debian, que dá mais compatibilidade
FROM python:3.12-slim


# Evita mensagens de cache e instala ferramentas de compilação necessárias
RUN apt-get update && \
    apt-get install -y gcc g++ libpq-dev build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Define diretório do app
WORKDIR /app

# Copia o requirements
COPY requirements.txt .

# Atualiza pip e instala dependências
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código
COPY . .

# Expõe a porta padrão do uvicorn
EXPOSE 8000

# Comando para rodar a API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
