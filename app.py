import os, json, logging, re
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from dateutil.parser import parse as parse_date
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret")
CORS(app)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Logging
logging.basicConfig(level=logging.INFO, filename="app.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load JSON data
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
except Exception as e:
    logger.critical(f"Gagal load JSON kampus: {e}")
    TRISAKTI = {}

# SymSpell (autocorrect)
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1)

# Helpers
def correct_typo(text):
    corrected = []
    for word in text.split():
        suggestions = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected.append(suggestions[0].term if suggestions else word)
    return " ".join(corrected)

def detect_language(text):
    try:
        return detect(text) if len(text.split()) > 1 else "id"
    except:
        return "id"

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    return re.sub(r"(https?://[^\s<>'\"()]+)", r"<a href='\1' target='_blank' class='link'>🔗 Klik di sini</a>", text)

def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

def get_current_registration_status():
    try:
        today = datetime.now().date()
        summary = []
        for jalur in TRISAKTI.get("registration", {}).get("paths", []):
            for wave in jalur.get("waves", []):
                start_str, end_str = [s.strip() for s in wave["period"].split(" - ")]
                start = parse_date(start_str, dayfirst=True).date()
                end = parse_date(end_str, dayfirst=True).date()
                name = wave["wave"]
                if today < start:
                    status = f"{name} ({jalur['name']}) akan dibuka {start.strftime('%d %B %Y')}."
                elif start <= today <= end:
                    status = f"{name} ({jalur['name']}) sedang berlangsung hingga {end.strftime('%d %B %Y')}."
                else:
                    status = f"{name} ({jalur['name']}) sudah ditutup {end.strftime('%d %B %Y')}."
                summary.append(status)
        return "\n".join(summary)
    except Exception as e:
        logger.warning(f"Gagal hitung status pendaftaran: {e}")
        return "Status pendaftaran tidak tersedia."

def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = json.load(open(file, encoding="utf-8")) if os.path.exists(file) else []
        history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg, "ai": ai_msg
        })
        json.dump(history, open(file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal simpan riwayat: {e}")

# Routes
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/chat")
def chat_room():
    return render_template("chat.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
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
        "latest": history[-5:]
    })

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("landing"))

@app.route("/api/chat", methods=["POST"])
def ai_reply():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Pesan kosong"}), 400

    corrected = correct_typo(message)
    lang = detect_language(message)
    category = get_category(corrected)
    status_summary = get_current_registration_status()

    if category == "brosur":
        url = request.host_url.rstrip("/") + "/download-brosur"
        reply = (
            "📄 Brosur resmi TMM tersedia!<br><br>"
            f"<a href='{url}' class='download-btn'>⬇️ Klik di sini untuk unduh</a>"
        )
        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang})

    system_prompt = (
        "Kamu adalah TIMU, AI interaktif TMM. Jawab ramah, tidak terlalu formal, dan berbasis data kampus.\n"
        f"Data: {json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Status Pendaftaran:\n{status_summary}"
    )
    prompt = (
        f"Tanggal: {datetime.now().strftime('%d %B %Y, %H:%M')}\n"
        f"Pesan: {corrected}\nBahasa: {lang.upper()}"
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={
            "temperature": 0.3, "top_p": 0.9, "max_output_tokens": 1024
        })
        result = model.generate_content(system_prompt + "\n\n" + prompt)
        reply = clean_response(result.text)
        reply = format_links(reply)

        if not reply.strip():
            reply = f"Maaf, saya belum punya info itu. Hubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."

        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang})

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini error: {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500

@app.route("/download-brosur")
def download_brosur():
    try:
        return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)
    except:
        return jsonify({"error": "Brosur tidak tersedia"}), 404

# Run
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)