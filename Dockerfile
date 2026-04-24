FROM python:3.11-slim

# Install LibreOffice + required system libs (slim layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    libreoffice-writer \
    fonts-liberation \
    fonts-dejavu \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects $PORT at runtime
CMD gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1
