FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema (Node.js y LibreOffice para generación de documentos)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    libreoffice \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Instalar las dependencias de Node.js dentro del motor de documentos
# Esto es vital para que factory.py pueda ejecutar los templates .js
RUN cd src/document_engine && npm install

EXPOSE 8000

# Healthcheck mejorado para detectar si el orquestador está listo
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Comando de inicio
CMD ["sh", "-c", "uvicorn src.api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
# Force deploy trigger
