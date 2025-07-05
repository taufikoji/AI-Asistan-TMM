# app.py (versi stabil dengan fix chat, auto sapa satu kali, dan endpoint API jalan)

import os, json, logging, re
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret")
CORS(app)

# Gemini setup
genai.configure(api_key=GEMINI_API_KEY)

# Load data kampus
try:
    with open("trisakti_info.json", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    TRISAKTI["current_context"]["date"] = datetime.now().strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = datetime.now().strftime("%H:%M WIB")
except:
    TRISAKTI = {}

# Symspell
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1)

# Helpers
def detect_language(text):
    try: return detect(text)
    except: return "unknown"

def correct_typo(text):
    return " ".join([
        symspell.lookup(w, Verbosity.CLOSEST, max_edit_distance=2)[0].term if symspell.lookup(w, Verbosity.CLOSEST, max_edit_distance=2) else w
        for w in text.split()
    ])

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    # Ganti URL mentah ke <a>
    return re.sub(r"(https?://[^\s<>'\"()]+)", r"<a href='\1' target='_blank' rel='noopener noreferrer'>🔗 Klik di sini</a>", text)

def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = json.load(open(file, encoding="utf-8")) if os.path.exists(file) else []
        history.append({"timestamp": datetime.now().isoformat(), "user": user_msg, "ai": ai_msg})
        json.dump(history, open(file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal simpan chat: {e}")

def get_category(msg):
    msg = msg.lower()
    for k, keywords in TRISAKTI.get("keywords", {}).items():
        if any(x in msg for x in keywords): return k
    return "general"

# Routes
@app.route("/")
def index(): return render_template("index.html")

@app.route("/landing")
def landing(): return render_template("landing.html", year=datetime.now().year)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message: return jsonify({"error": "Pesan kosong."}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    if 'conversation' not in session:
        session['conversation'] = []
        session['greeted'] = False

    session['conversation'].append({"user": corrected})
    if len(session['conversation']) > 5:
        session['conversation'] = session['conversation'][-5:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})

    # Brosur
    if kategori == "brosur":
        brosur_url = f"{request.host_url.rstrip('/')}/download-brosur".replace("http://", "https://")
        reply = (
            "📄 Brosur resmi Trisakti School of Multimedia tersedia:<br><br>"
            f"<a href='{brosur_url}' class='download-btn' target='_blank'>⬇️ Unduh Brosur</a><br><br>"
            "Jika tidak bisa mengakses, salin dan buka link tersebut."
        )
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    # Prompt ke Gemini
    system_prompt = (
        "Anda adalah TIMU, asisten AI resmi Trisakti School of Multimedia (TMM). "
        "Jawab dengan ramah dan profesional sesuai bahasa pengguna.\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Percakapan sebelumnya:\n{json.dumps(session['conversation'], ensure_ascii=False)}"
    )

    prompt = (
        f"\n\nCatatan tambahan:\n"
        f"- Bahasa pengguna: {lang}\n"
        f"- Pertanyaan: \"{corrected}\"\n"
        f"- Kategori: {kategori}\n"
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        result = model.generate_content(system_prompt + prompt)
        reply = clean_response(result.text.strip()).replace("TSM", "TMM")
        reply = format_links(reply)

        # fallback jika kosong
        if not reply:
            reply = f"Maaf, saya belum bisa menjawab. Silakan hubungi admin via WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."

        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini API error: {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"Error internal: {e}")
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
        "latest": history[-5:] if len(history) >= 5 else history
    })

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ========== RUN ==========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)