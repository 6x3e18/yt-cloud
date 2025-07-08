FROM python:3.11-slim

# Installiere FFmpeg und seine Abhängigkeiten
# Dies ist entscheidend, damit die static_ffmpeg-Binärdateien ausgeführt werden können.
# Wir installieren hier nicht unbedingt, um diese ffmpeg-Binary direkt zu nutzen,
# sondern um sicherzustellen, dass alle dynamischen Bibliotheken, die static_ffmpeg's
# Binaries benötigen, im System vorhanden sind.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        tar \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /app

# Projektdateien kopieren
COPY requirements.txt /app/

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den Rest der Anwendung
COPY . /app

# Flask-App starten
CMD ["python", "main.py"]
