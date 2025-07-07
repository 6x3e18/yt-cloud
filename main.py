import os
from flask import Flask, render_template, request, redirect, url_for, session
from webdav3.client import Client
import yt_dlp
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "changeme")

USERNAME = os.getenv("APP_USERNAME", "admin")
PASSWORD = os.getenv("APP_PASSWORD", "password")

@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        url = request.form["url"]
        try:
            filename = download_audio(url)
            upload_to_webdav(filename)
            return f"Download erfolgreich: {os.path.basename(filename)}"
        except Exception as e:
            return f"Fehler: {e}"

    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == USERNAME and request.form["password"] == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return "Falsche Zugangsdaten."
    return render_template("login.html")

def download_audio(url):
    output_template = "/tmp/downloads/%(title)s.%(ext)s"

    os.makedirs("/tmp/downloads", exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'aac',
                'preferredquality': '0',
            },
            {'key': 'EmbedThumbnail'},
            {'key': 'FFmpegMetadata'}
        ],
        'outtmpl': output_template,
        'writethumbnail': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace(".webm", ".m4a")  # ggf. anpassen
        return filename

def upload_to_webdav(local_path):
    options = {
        'webdav_hostname': os.getenv("WEBDAV_HOST"),
        'webdav_login': os.getenv("WEBDAV_LOGIN"),
        'webdav_password': os.getenv("WEBDAV_PASSWORD")
    }

    client = Client(options)
    remote_path = f"/Soundcloud/{os.path.basename(local_path)}"
    client.upload_sync(remote_path=remote_path, local_path=local_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
