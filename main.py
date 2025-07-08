FROM python:3.11-slim

# Installiere FFmpeg und eine breitere Palette seiner Abhängigkeiten.
# Dies ist entscheidend, damit die static_ffmpeg-Binärdateien ausgeführt werden können.
# Wir stellen sicher, dass alle dynamischen Bibliotheken, die FFmpeg benötigt, vorhanden sind.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        tar \
        ca-certificates \
        # Allgemeine Bibliotheken für FFmpeg und Bildverarbeitung (für Thumbnails)
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libxext6 \
        libxrender1 \
        libglib2.0-0 \
        libsm6 \
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
        # Zusätzliche Codec-Bibliotheken, die oft für yt-dlp Post-Processing nützlich sind
        libavcodec-extra \
        libavformat-extra \
        libavutil-extra \
        libswresample-extra \
        libswscale-extra \
        libpostproc-extra \
        libavdevice-extra \
        # Für bestimmte Audio-Codecs (z.B. AAC)
        libfdk-aac1 \
        libmp3lame0 \
        libopus0 \
        libvorbis0a \
        libvpx7 \
        libx264-164 \
        libx265-199 \
        # Bereinigen des APT-Caches, um die Image-Größe zu reduzieren
        && \
    rm -rf /var/lib/apt/lists/*

# Arbeitsverzeichnis setzen
WORKDIR /app

# Projektdateien kopieren
COPY requirements.txt /app/

# Python-Abhängigkeiten installieren
# Stellen Sie sicher, dass static_ffmpeg in Ihrer requirements.txt ist, da wir es verwenden.
RUN pip install --no-cache-dir -r requirements.txt

# Kopiere den Rest der Anwendung
COPY . /app

# Flask-App starten
CMD ["python", "main.py"]
