FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY app/ ./app/
COPY data/ ./data/
COPY start.sh .

# Crear carpeta data si no existe
RUN mkdir -p /app/data

# Exponer puerto
EXPOSE 8000

# Variables de entorno
ENV PORT=8000
ENV HOST=0.0.0.0

# Comando de inicio
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
