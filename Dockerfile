FROM python:3.11-slim

# Installiere System-Abhängigkeiten
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        tar \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ffmpeg & ffprobe von yt-dlp GitHub-Release laden
RUN curl -L https://github.com/yt-dlp/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-linux64-gpl.tar.xz -o ffmpeg.tar.xz && \
    mkdir -p /opt/ffmpeg && \
    tar -xf ffmpeg.tar.xz --strip-components=1 -C /opt/ffmpeg && \
    ln -s /opt/ffmpeg/ffmpeg /usr/local/bin/ffmpeg && \
    ln -s /opt/ffmpeg/ffprobe /usr/local/bin/ffprobe && \
    rm ffmpeg.tar.xz

# Arbeitsverzeichnis setzen
WORKDIR /app

# Projektdateien kopieren
COPY . /app

# Python-Abhängigkeiten installieren
RUN pip install --no-cache-dir -r requirements.txt

# Flask-App starten
CMD ["python", "main.py"]
