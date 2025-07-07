FROM python:3.11-slim

# Installiere minimale System-Abhängigkeiten
# curl, tar, ca-certificates sind nützlich, falls static_ffmpeg diese für den Download benötigt.
# (static_ffmpeg verwendet meist requests, aber diese Pakete schaden nicht)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        tar \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /app

# Projektdateien kopieren
# Es ist gute Praxis, nur die requirements.txt zuerst zu kopieren und zu installieren,
# um den Layer-Cache von Docker optimal zu nutzen.
COPY requirements.txt /app/

# Python-Abhängigkeiten installieren
# static_ffmpeg wird hier installiert und kümmert sich um ffmpeg/ffprobe zur Laufzeit
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den Rest der Anwendung
COPY . /app

# Flask-App starten
# Stelle sicher, dass main.py der korrekte Startpunkt deiner Anwendung ist
CMD ["python", "main.py"]
