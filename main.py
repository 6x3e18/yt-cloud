import os
import logging
import shutil
from flask import Flask, render_template, request, redirect, url_for, session, flash
from webdav3.client import Client
import sys
import glob
# from static_ffmpeg import add_paths # Diese Zeile wird entfernt, da wir static_ffmpeg nicht mehr verwenden
import yt_dlp
from dotenv import load_dotenv

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Lade .env Variablen
load_dotenv()

# Initialisiere ffmpeg/ffprobe
# Wir verlassen uns darauf, dass ffmpeg/ffprobe systemweit installiert und im PATH sind.
# Daher benötigen wir keine spezielle Initialisierungslogik mehr für static_ffmpeg.
FFMPEG_EXECUTABLE_PATH = shutil.which("ffmpeg")
FFPROBE_EXECUTABLE_PATH = shutil.which("ffprobe")

if FFMPEG_EXECUTABLE_PATH is None or FFPROBE_EXECUTABLE_PATH is None:
    logging.critical("CRITICAL: FFmpeg oder FFprobe wurde im System-PATH NICHT gefunden. Bitte stellen Sie sicher, dass FFmpeg installiert ist.")
    # Optional: Hier könnten Sie die Anwendung beenden oder einen Fehler auf der Webseite anzeigen
else:
    logging.info(f"FFmpeg Initialisierung abgeschlossen. Verwende systemweiten FFmpeg: {FFMPEG_EXECUTABLE_PATH}")
    logging.info(f"Verwende systemweiten FFprobe: {FFPROBE_EXECUTABLE_PATH}")

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

    # Da FFmpeg/FFprobe jetzt systemweit installiert sind, sollte yt-dlp sie automatisch finden.
    # Wir entfernen die expliziten Pfadangaben aus den ydl_opts.
    logging.info(f"FFmpeg/FFprobe sollten jetzt über PATH gefunden werden.")

    ydl_opts = {
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
