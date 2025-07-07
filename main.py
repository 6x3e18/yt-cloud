import os
import logging
import shutil
from flask import Flask, render_template, request, redirect, url_for, session, flash
from webdav3.client import Client
import sys
import platform
from static_ffmpeg import add_paths
import yt_dlp
from dotenv import load_dotenv

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lade Umgebungsvariablen aus .env
load_dotenv()

# Initialisiere ffmpeg/ffprobe
def get_ffmpeg_path():
    try:
        add_paths()  # Fügt static_ffmpeg/bin zum PATH hinzu

        base_dir = os.path.dirname(sys.modules["static_ffmpeg"].__file__)
        os_name = platform.system().lower()
        bin_dir = os.path.join(base_dir, "bin", os_name)

        ffmpeg = os.path.join(bin_dir, "ffmpeg")
        ffprobe = os.path.join(bin_dir, "ffprobe")

        if os.path.isfile(ffmpeg) and os.access(ffmpeg, os.X_OK) and \
           os.path.isfile(ffprobe) and os.access(ffprobe, os.X_OK):
            logging.info(f"✔️ FFmpeg gefunden unter: {ffmpeg}")
            return bin_dir
        else:
            raise FileNotFoundError("static_ffmpeg installiert, aber Binärdateien nicht vorhanden oder nicht ausführbar.")

    except Exception as e:
        logging.warning(f"⚠️ static_ffmpeg fehlgeschlagen: {e}")

        # Fallback: Suche im System
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg and ffprobe:
            logging.info(f"✔️ System-FFmpeg gefunden unter: {ffmpeg}")
            return os.path.dirname(ffmpeg)
        else:
            logging.error("❌ Kein funktionierendes FFmpeg gefunden.")
            return None

ffmpeg_path = get_ffmpeg_path()
