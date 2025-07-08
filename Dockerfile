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
        ca-certificates \
        # Hinzugefügte Bibliotheken, die oft von FFmpeg benötigt werden
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libxext6 \
        libxrender1 \
        libglib2.0-0 \
        libsm6 \
        libxrender1 \
        libxext6 \
        libxrandr2 \
        libxfixes3 \
        libxi6 \
        libxcursor1 \
        libxdamage1 \
        libxcomposite1 \
        libnss3 \
        libatk1.0-0 \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libxss1 \
        libxtst6 \
        # Optional: Weitere Codec-Bibliotheken, falls spezifische Codecs fehlen
        # libavcodec-extra \
        # libavformat-extra \
        # libavutil-extra \
        # libswresample-extra \
        # libswscale-extra \
        # libpostproc-extra \
        # libavdevice-extra \
        && \
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
