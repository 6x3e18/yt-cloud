import os
import logging
import shutil


ffmpeg_dir = "/opt/venv/lib/python3.12/site-packages/static_ffmpeg/bin/linux/"
os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

from flask import Flask, render_template, request, redirect, url_for, session, flash
from webdav3.client import Client
import sys
import glob
from static_ffmpeg import add_paths
import yt_dlp
FFMPEG_PATH = ffmpeg_dir
from dotenv import load_dotenv
import subprocess

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lade .env Variablen
load_dotenv()

# Initialisiere ffmpeg/ffprobe mit Fallback
# Globale Variablen zum Speichern der gefundenen ffmpeg/ffprobe ausführbaren Pfade
FFMPEG_EXECUTABLE_PATH = None
FFPROBE_EXECUTABLE_PATH = None

try:
    ffmpeg_version = subprocess.check_output([FFMPEG_EXECUTABLE_PATH, "-version"], text=True)
    logging.info(f"FFmpeg Version:\n{ffmpeg_version}")
except Exception as e:
    logging.error(f"FFmpeg nicht ausführbar: {e}")


try:
    # static_ffmpeg.add_paths() gibt das Verzeichnis zurück, in dem es die Binärdateien platziert hat
    ffmpeg_bin_dir = add_paths()

    # Überprüfe, ob ffmpeg_bin_dir ein gültiger Pfad (String) ist und ein Verzeichnis ist
    if isinstance(ffmpeg_bin_dir, str) and os.path.isdir(ffmpeg_bin_dir):
        # Konstruiere den vollständigen, absoluten Pfad zu den ffmpeg und ffprobe ausführbaren Dateien
        static_ffmpeg_path = os.path.join(ffmpeg_bin_dir, 'ffmpeg')
        static_ffprobe_path = os.path.join(ffmpeg_bin_dir, 'ffprobe')

        # Priorisiere static_ffmpeg Pfade, wenn sie gültig sind
        if os.path.exists(static_ffmpeg_path) and os.path.isfile(static_ffmpeg_path) and os.access(static_ffmpeg_path, os.X_OK):
            FFMPEG_EXECUTABLE_PATH = static_ffmpeg_path
            FFPROBE_EXECUTABLE_PATH = static_ffprobe_path
            logging.info(f"FFmpeg ausführbarer Pfad (static_ffmpeg) erfolgreich gefunden und ist ausführbar: {FFMPEG_EXECUTABLE_PATH}")
        else:
            logging.warning(f"Static FFmpeg Pfad ({static_ffmpeg_path}) ist nicht gültig oder nicht ausführbar. Versuche systemweiten FFmpeg.")
            # Fallback zu systemweitem ffmpeg
            ffmpeg_bin_sys = shutil.which("ffmpeg")
            ffprobe_bin_sys = shutil.which("ffprobe")

            if ffmpeg_bin_sys and ffprobe_bin_sys:
                FFMPEG_EXECUTABLE_PATH = ffmpeg_bin_sys
                FFPROBE_EXECUTABLE_PATH = ffprobe_bin_sys
                logging.info(f"Verwende systemweiten FFmpeg: {FFMPEG_EXECUTABLE_PATH}")
            else:
                raise RuntimeError("Kein ffmpeg/ffprobe gefunden (weder static_ffmpeg noch systemweit)")
    else:
        logging.warning(f"static_ffmpeg.add_paths() gab keinen gültigen Pfad zurück ({ffmpeg_bin_dir}). Versuche systemweiten FFmpeg.")
        # Fallback zu systemweitem ffmpeg, da static_ffmpeg versagt hat
        ffmpeg_bin_sys = shutil.which("ffmpeg")
        ffprobe_bin_sys = shutil.which("ffprobe")

        if ffmpeg_bin_sys and ffprobe_bin_sys:
            FFMPEG_EXECUTABLE_PATH = ffmpeg_bin_sys
            FFPROBE_EXECUTABLE_PATH = ffprobe_bin_sys
            logging.info(f"Verwende systemweiten FFmpeg: {FFMPEG_EXECUTABLE_PATH}")
        else:
            raise RuntimeError("Kein ffmpeg/ffprobe gefunden (weder static_ffmpeg noch systemweit)")

    # Sicherstellen der Ausführungsrechte für die gefundenen Binärdateien
    if FFMPEG_EXECUTABLE_PATH and os.path.exists(FFMPEG_EXECUTABLE_PATH) and os.path.isfile(FFMPEG_EXECUTABLE_PATH):
        try:
            os.chmod(FFMPEG_EXECUTABLE_PATH, 0o755) # Lese-, Schreib-, Ausführungsrechte für Besitzer, Lese-/Ausführungsrechte für Gruppe/andere
            logging.info(f"Ausführungsrechte für FFmpeg gesetzt: {FFMPEG_EXECUTABLE_PATH}")
        except Exception as chmod_e:
            logging.warning(f"Konnte Ausführungsrechte für FFmpeg nicht setzen: {chmod_e}")
    if FFPROBE_EXECUTABLE_PATH and os.path.exists(FFPROBE_EXECUTABLE_PATH) and os.path.isfile(FFPROBE_EXECUTABLE_PATH):
        try:
            os.chmod(FFPROBE_EXECUTABLE_PATH, 0o755)
            logging.info(f"Ausführungsrechte für FFprobe gesetzt: {FFPROBE_EXECUTABLE_PATH}")
        except Exception as chmod_e:
            logging.warning(f"Konnte Ausführungsrechte für FFprobe nicht setzen: {chmod_e}")

    # PATH nur einmal und konsistent hinzufügen, wenn die Pfade erfolgreich gefunden wurden
    if FFMPEG_EXECUTABLE_PATH:
        # Extrahiere das Verzeichnis des gefundenen ffmpeg Pfades
        found_ffmpeg_dir = os.path.dirname(FFMPEG_EXECUTABLE_PATH)
        # Füge das Verzeichnis am ANFANG des PATH hinzu, um Priorität zu gewährleisten
        if found_ffmpeg_dir not in os.environ['PATH'].split(os.pathsep): # Überprüfe, ob es nicht bereits im PATH ist
            os.environ['PATH'] = found_ffmpeg_dir + os.pathsep + os.environ['PATH']
            logging.info(f"FFmpeg/FFprobe binary directory '{found_ffmpeg_dir}' zum PATH hinzugefügt.")


except Exception as e:
    # Protokolliere den genauen Fehler, der das Problem verursacht hat
    logging.error(f"Fehler bei FFmpeg/FFprobe Initialisierung: {e}", exc_info=True)
    FFMPEG_EXECUTABLE_PATH = None
    FFPROBE_EXECUTABLE_PATH = None

# Nach dem try...except Block der FFmpeg Initialisierung
if FFMPEG_EXECUTABLE_PATH is None:
    logging.critical("CRITICAL: FFmpeg/FFprobe konnte NICHT initialisiert werden! FFMPEG_EXECUTABLE_PATH ist immer noch None.")
else:
    logging.info(f"FFmpeg Initialisierung abgeschlossen. FFMPEG_EXECUTABLE_PATH: {FFMPEG_EXECUTABLE_PATH}")


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
            
        # Verwende den global ermittelten ffmpeg Pfad
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

    # Stelle sicher, dass FFMPEG_EXECUTABLE_PATH und FFPROBE_EXECUTABLE_PATH gesetzt sind
    if not FFMPEG_EXECUTABLE_PATH or not FFPROBE_EXECUTABLE_PATH:
        raise RuntimeError("FFmpeg oder FFprobe ist nicht verfügbar, kann keinen Download durchführen.")

    # Logging der expliziten Pfade
    logging.info(f"FFmpeg/FFprobe sollten jetzt über PATH gefunden werden.")

    ydl_opts = {
        'ffmpeg_location': FFMPEG_PATH,
        'format': 'bestaudio/best',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'aac',
                'preferredquality': '0',
            },
            {'key': 'EmbedThumbnail'},
            {'key': 'FFmpegMetadata'}
        ],
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'writethumbnail': True,
        'quiet': False,
        'no_warnings': False,
        'verbose': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        info = ydl.extract_info(url, download=True)
        final_filename = ydl.prepare_filename(info)

        # Besserer Weg, um die tatsächliche Ausgabedatei nach der Nachbearbeitung zu erhalten
        if 'requested_downloads' in info and info['requested_downloads']:
            actual_filename_list = [d['filepath'] for d in info['requested_downloads'] if 'filepath' in d]
            if actual_filename_list:
                actual_filename = actual_filename_list[0]
                logging.info(f"Konvertierter Dateipfad aus info['requested_downloads']: {actual_filename}")
                return actual_filename
            
        # Fallback für andere Szenarien oder wenn 'requested_downloads' nicht vorhanden/leer ist
        elif 'filepath' in info:
            actual_filename = info['filepath']
            logging.info(f"Konvertierter Dateipfad aus info['filepath']: {actual_filename}")
            return actual_filename


        # Ursprüngliche Fallback-Logik, könnte für Randfälle noch benötigt werden
        base_filename_without_ext = os.path.splitext(final_filename)[0]
        expected_filename = f"{base_filename_without_ext}.m4a" # Angenommen, AAC führt zu .m4a

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
