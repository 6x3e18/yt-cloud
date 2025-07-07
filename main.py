import os
import logging
import shutil
from flask import Flask, render_template, request, redirect, url_for, session, flash
from webdav3.client import Client
import sys
import glob
from static_ffmpeg import add_paths
import yt_dlp
from dotenv import load_dotenv

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lade .env Variablen
load_dotenv()

# Initialisiere ffmpeg/ffprobe mit Fallback
ffmpeg_path = None

try:
    add_paths()

    # Mögliche statische Folder finden
    venv_site = os.path.dirname(sys.modules['static_ffmpeg'].__file__)
    pattern = os.path.join(venv_site, 'bin', '*')
    candidates = glob.glob(pattern)

    # Filtere ffmpeg / ffprobe Dateien
    bins = [p for p in candidates if os.path.basename(p) in ('ffmpeg', 'ffprobe') or os.path.basename(p).startswith('ffmpeg')]

    if bins:
        ffmpeg_dir = os.path.dirname(bins[0])
        ffmpeg_path = ffmpeg_dir
        logging.info(f"Verwende FFmpeg aus static_ffmpeg im Verzeichnis: {ffmpeg_path}")
    else:
        # Fallback auf Systemffmpeg
        ffmpeg_bin = shutil.which("ffmpeg")
        ffprobe_bin = shutil.which("ffprobe")
        if ffmpeg_bin and ffprobe_bin:
            ffmpeg_path = os.path.dirname(ffmpeg_bin)
            logging.info(f"Verwende systemweiten FFmpeg: {ffmpeg_bin}")
        else:
            raise RuntimeError("Kein ffmpeg/ffprobe gefunden (weder static_ffmpeg noch systemweit)")

except Exception as e:
    logging.error(f"Fehler bei FFmpeg/FFprobe Initialisierung: {e}")
    ffmpeg_path = None


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
            
        if not ffmpeg_path:
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
    logging.info(f"Using FFmpeg path for yt-dlp: {ffmpeg_path}")

    # yt-dlp wird das Format basierend auf 'preferredcodec' festlegen
    # Die Dateierweiterung wird automatisch korrekt sein (z.B. .m4a)
    ydl_opts = {
        'format': 'bestaudio/best',  # Versuch 'bestaudio', fallback auf 'best'
        'ffmpeg_location': ffmpeg_path,
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

        if 'files' in info and info['files']:
            converted_file = info['files'][0]
            if 'filepath' in converted_file:
                actual_filename = converted_file['filepath']
                logging.info(f"Konvertierter Dateipfad aus info['files']: {actual_filename}")
                return actual_filename

        base_filename_without_ext = os.path.splitext(final_filename)[0]
        expected_filename = f"{base_filename_without_ext}.m4a"

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
    remote_dir = "/Soundcloud"
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
