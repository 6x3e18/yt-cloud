FROM python:3.11-slim

# Systempakete installieren, inkl. ffmpeg & ffprobe
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        wget \
        gnupg && \
    rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /app

# Projektdateien kopieren
COPY . /app

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Container starten mit Flask-App
CMD ["python", "main.py"]
