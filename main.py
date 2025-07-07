import os
import logging
import shutil
from flask import Flask, render_template, request, redirect, url_for, session, flash
from webdav3.client import Client
import sys
import glob
from static_ffmpeg import add_paths # Keep this import, but we'll use its return value directly
import yt_dlp
from dotenv import load_dotenv

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lade .env Variablen
load_dotenv()

# Initialisiere ffmpeg/ffprobe mit Fallback
# Global variable to store the found ffmpeg executable path
FFMPEG_EXECUTABLE_PATH = None
FFPROBE_EXECUTABLE_PATH = None

try:
    # static_ffmpeg.add_paths() returns the directory where it placed binaries
   add_paths()  # Nur zum PATH hinzufügen, gibt keinen Pfad zurück

# Manuell Pfad setzen (standardmäßig entpackt in dieses Verzeichnis)
ffmpeg_bin_dir = os.path.join(os.path.dirname(__file__), "venv/lib/python3.12/site-packages/static_ffmpeg/bin")
FFMPEG_EXECUTABLE_PATH = os.path.join(ffmpeg_bin_dir, "ffmpeg")
FFPROBE_EXECUTABLE_PATH = os.path.join(ffmpeg_bin_dir, "ffprobe")


    # Verify if the files exist and are executable (optional, but good for debugging startup)
    if os.path.exists(FFMPEG_EXECUTABLE_PATH) and os.path.isfile(FFMPEG_EXECUTABLE_PATH) and os.access(FFMPEG_EXECUTABLE_PATH, os.X_OK):
        logging.info(f"FFmpeg ausführbarer Pfad erfolgreich gefunden und ist ausführbar: {FFMPEG_EXECUTABLE_PATH}")
    else:
        # Fallback to system-wide ffmpeg if static_ffmpeg path isn't valid/executable
        ffmpeg_bin_sys = shutil.which("ffmpeg")
        ffprobe_bin_sys = shutil.which("ffprobe")
        if ffmpeg_bin_sys and ffprobe_bin_sys:
            FFMPEG_EXECUTABLE_PATH = ffmpeg_bin_sys
            FFPROBE_EXECUTABLE_PATH = ffprobe_bin_sys
            logging.info(f"Verwende systemweiten FFmpeg: {FFMPEG_EXECUTABLE_PATH}")
        else:
            raise RuntimeError("Kein ffmpeg/ffprobe gefunden (weder static_ffmpeg noch systemweit)")

except Exception as e:
    logging.error(f"Fehler bei FFmpeg/FFprobe Initialisierung: {e}")
    FFMPEG_EXECUTABLE_PATH = None
    FFPROBE_EXECUTABLE_PATH = None


# Flask Setup
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "changeme")

# Zugangsdaten aus .env
USERNAME = os.getenv("APP_USERNAME", "admin")
PASSWORD = os.getenv("APP_PASSWORD", "password")

# WebDAV Konfiguration
WEBDAV_HOST = os.getenv("WEBDAV_HOST")
WEBDAV_LOGIN = os.getenv("WEBDAV_LOGIN")
WEBDAV_PASSWORD = os.getenv("WEBDAV_PASSWORD")

if not all([WEBDAV_HOST, WEBDAV_LOGIN, WEBDAV_PASSWORD]):
    logging.warning("WebDAV Zugangsdaten sind nicht vollständig in den Umgebungsvariablen gesetzt.")

@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        url = request.form["url"]
        if not url:
            flash("Bitte gib eine URL ein.", "error")
            return render_template("index.html")
            
        # Use the globally determined ffmpeg path
        if not FFMPEG_EXECUTABLE_PATH: 
            flash("❌ Fehler: FFmpeg ist nicht verfügbar. Bitte kontaktiere den Administrator.", "error")
            return render_template("index.html")

        try:
            filename = download_audio(url)
            flash(f"✅ Download erfolgreich: {os.path.basename(filename)}", "success")
            
            # Optional: Direktes Hochladen nach erfolgreichem Download
            try:
                upload_to_webdav(filename)
                flash(f"✅ Upload zu WebDAV erfolgreich: {os.path.basename(filename)}", "success")
            except Exception as upload_e:
                logging.error(f"Fehler beim Hochladen zu WebDAV: {upload_e}")
                flash(f"⚠️ Download erfolgreich, aber Fehler beim Upload zu WebDAV: {upload_e}", "warning")

        except yt_dlp.utils.DownloadError as e:
            logging.error(f"yt-dlp Download-Fehler für URL {url}: {e}")
            flash(f"❌ Download-Fehler (yt-dlp): {e}", "error")
        except yt_dlp.utils.PostProcessingError as e:
            logging.error(f"FFmpeg/Post-Processing Fehler für URL {url}: {e}")
            flash(f"❌ Konvertierungsfehler (FFmpeg/Post-Processing): {e}. Überprüfe FFmpeg.", "error")
        except Exception as e:
            logging.error(f"Ein unerwarteter Fehler ist aufgetreten für URL {url}: {e}")
            flash(f"❌ Ein unerwarteter Fehler ist aufgetreten: {e}", "error")
            
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == USERNAME and request.form["password"] == PASSWORD:
            session["logged_in"] = True
            flash("Erfolgreich eingeloggt!", "success")
            return redirect(url_for("index"))
        else:
            flash("❌ Falsche Zugangsdaten.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    flash("Du wurdest ausgeloggt.", "info")
    return redirect(url_for("login"))

def download_audio(url):
    download_dir = "/tmp/downloads"
    os.makedirs(download_dir, exist_ok=True)
    logging.info(f"Starte Audio-Download für URL: {url}")
    # Use the global FFMPEG_EXECUTABLE_PATH here
    logging.info(f"Using FFmpeg executable path for yt-dlp: {FFMPEG_EXECUTABLE_PATH}") 

    # yt-dlp wird das Format basierend auf 'preferredcodec' festlegen
    # Die Dateierweiterung wird automatisch korrekt sein (z.B. .m4a)
    ydl_opts = {
        'format': 'bestaudio/best',  # Versuch 'bestaudio', fallback auf 'best'
        # Pass the full executable path, not just the directory
        'ffmpeg_location': FFMPEG_EXECUTABLE_PATH, 
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'aac',
                'preferredquality': '0',  # Beste Qualität
            },
            {'key': 'EmbedThumbnail'},
            {'key': 'FFmpegMetadata'}
        ],
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'writethumbnail': True,
        'quiet': False,  # Setze auf True für weniger Konsolenausgabe von yt-dlp
        'no_warnings': False,  # Setze auf True für weniger Warnungen
        'verbose': False  # Setze auf True für detaillierte yt-dlp Logs (gut zum Debuggen)
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        final_filename = ydl.prepare_filename(info)

        # Better way to get the actual output file after post-processing
        # yt-dlp stores the actual output files under 'requested_downloads' or directly in 'info'
        if 'requested_downloads' in info and info['requested_downloads']:
            actual_filename_list = [d['filepath'] for d in info['requested_downloads'] if 'filepath' in d]
            if actual_filename_list:
                actual_filename = actual_filename_list[0]
                logging.info(f"Konvertierter Dateipfad aus info['requested_downloads']: {actual_filename}")
                return actual_filename
        
        # Fallback for other scenarios or if 'requested_downloads' is not present/empty
        elif 'filepath' in info: # Some versions or types might put it directly here
             actual_filename = info['filepath']
             logging.info(f"Konvertierter Dateipfad aus info['filepath']: {actual_filename}")
             return actual_filename


        # Original fallback logic, might still be needed for edge cases
        base_filename_without_ext = os.path.splitext(final_filename)[0]
        expected_filename = f"{base_filename_without_ext}.m4a" # Assuming AAC leads to .m4a

        if os.path.exists(expected_filename):
            logging.info(f"Erwarteter Dateipfad {expected_filename} existiert.")
            return expected_filename
        else:
            logging.warning(f"Konnte den konvertierten Dateipfad nicht eindeutig bestimmen. Verwende den initialen Pfad: {final_filename}")
            return final_filename


def upload_to_webdav(local_path):
    if not all([WEBDAV_HOST, WEBDAV_LOGIN, WEBDAV_PASSWORD]):
        raise ValueError("WebDAV Zugangsdaten sind nicht vollständig konfiguriert.")

    options = {
        'webdav_hostname': WEBDAV_HOST,
        'webdav_login': WEBDAV_LOGIN,
        'webdav_password': WEBDAV_PASSWORD,
        'disable_check_cert': True # Nur für Entwicklung/Testzwecke, NICHT in Produktion!
                                   # Wenn dein WebDAV ein gültiges SSL-Zertifikat hat, entferne dies.
    }

    client = Client(options)
    
    # Sicherstellen, dass der Zielpfad auf dem WebDAV existiert
    remote_dir = "/Soundcloud" # Consider making this configurable via env var
    if not client.check(remote_dir):
        logging.info(f"Erstelle WebDAV-Verzeichnis: {remote_dir}")
        client.mkdir(remote_dir)

    remote_path = f"{remote_dir}/{os.path.basename(local_path)}"
    logging.info(f"Starte Upload von {local_path} zu WebDAV: {remote_path}")
    client.upload_sync(remote_path=remote_path, local_path=local_path)
    logging.info(f"Upload von {local_path} zu {remote_path} erfolgreich.")
    
    # Optional: Lokale Datei nach erfolgreichem Upload löschen
    try:
        os.remove(local_path)
        logging.info(f"Lokale Datei {local_path} nach Upload gelöscht.")
    except Exception as e:
        logging.warning(f"Konnte lokale Datei {local_path} nicht löschen: {e}")

if __name__ == "__main__":
    # Stelle sicher, dass der Download-Ordner bei jedem Start existiert
    os.makedirs("/tmp/downloads", exist_ok=True)
    
    # Debug-Modus ist gut für die Entwicklung, aber NICHT für die Produktion
    # app.run(host="0.0.0.0", port=5000, debug=True) 
    app.run(host="0.0.0.0", port=5000)
