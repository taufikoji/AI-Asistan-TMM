# app.py
import os
import json
import logging
import re
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="app.log")
logger = logging.getLogger(__name__)

# Load env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-secret-key")
CORS(app)

# Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")
    raise

# Load JSON kampus
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    TRISAKTI["current_context"]["date"] = datetime.now().strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = datetime.now().strftime("%H:%M WIB")
except Exception as e:
    logger.critical(f"Gagal load JSON kampus: {e}")
    TRISAKTI = {}

# SymSpell
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
dictionary_path = "indonesia_dictionary_3000.txt"
if not symspell.load_dictionary(dictionary_path, term_index=0, count_index=1):
    logger.warning("Gagal load kamus SymSpell.")

# Utility
def detect_language(text):
    try: return detect(text)
    except: return "unknown"

def correct_typo(text):
    return " ".join([
        symspell.lookup(w, Verbosity.CLOSEST, 2)[0].term if symspell.lookup(w, Verbosity.CLOSEST, 2) else w
        for w in text.split()
    ])

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    pattern = re.compile(r"(https?://[^\s<>'\"]+)")
    urls = list(set(pattern.findall(text)))
    for url in urls:
        text = text.replace(url, f"<a href='{url}' target='_blank' rel='noopener noreferrer'>🔗 Klik di sini</a>")
    return text

def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = json.load(open(file, "r", encoding="utf-8")) if os.path.exists(file) else []
        history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "ai": ai_msg
        })
        json.dump(history, open(file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal menyimpan chat: {e}")

def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/landing")
def landing():
    return render_template("landing.html", year=datetime.now().year)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    session.setdefault("conversation", [])
    session["conversation"].append({"user": corrected})
    session["conversation"] = session["conversation"][-5:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})

    if kategori == "brosur":
        base_url = request.host_url.replace("http://", "https://", 1).rstrip("/")
        brosur_url = f"{base_url}/download-brosur"
        reply = (
            "📄 Brosur resmi Trisakti School of Multimedia telah siap!<br><br>"
            f"<a href='{brosur_url}' class='download-btn' target='_blank'>⬇️ Klik di sini untuk mengunduh brosur</a><br><br>"
            "Jika tidak bisa mengakses, salin dan buka link ini di browser Anda."
        )
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Jawab dengan ramah, informatif, dan profesional dalam bahasa pengguna. "
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n"
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Percakapan sebelumnya: {json.dumps(session['conversation'], ensure_ascii=False)}"
    )

    prompt = (
        f"- Bahasa pengguna: {lang}\n"
        f"- Kalimat asli: \"{message}\"\n"
        f"- Koreksi: \"{corrected}\"\n"
        f"- Kategori: {kategori}\n"
        "Jawab sopan dan bantu lanjut diskusi."
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={"temperature": 0.3})
        result = model.generate_content(system_prompt + "\n\n" + prompt)
        reply = clean_response(result.text.strip().replace("TSM", "TMM"))
        reply = format_links(reply)

        if not reply:
            reply = f"Maaf, belum ada informasi yang sesuai. Hubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."

        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Internal Error] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

@app.route("/download-brosur")
def download_brosur():
    path = os.path.join("static", "brosur_tmm.pdf")
    if not os.path.exists(path):
        return jsonify({"error": "Brosur tidak tersedia."}), 404
    return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)

# Admin
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_stats"))
        return render_template("login.html", error="Password salah.")
    return render_template("login.html")

@app.route("/admin/stats")
def admin_stats():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))
    try:
        with open("chat_history.json", "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []
    return render_template("stats.html", stats={
        "total_chats": len(history),
        "latest": history[-5:] if history else []
    })

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # Default ke 5000 jika tidak diset
    app.run(host="0.0.0.0", port=port, debug=True)