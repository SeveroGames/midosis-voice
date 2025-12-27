# En asistente_voz_backend/Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Instalar dependencias del sistema para Whisper y TTS
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements_backend.txt .
RUN pip install --no-cache-dir -r requirements_backend.txt

# Descargar modelo spaCy español
RUN python -m spacy download es_core_news_sm

# Copiar aplicación
COPY . .

# Exponer puerto
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]