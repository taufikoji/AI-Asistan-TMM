import os, json, logging, re
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
from dateutil.parser import parse as parse_date
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity

# === Logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="app.log")
logger = logging.getLogger(__name__)

# === Load environment ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret123")
CORS(app)

# === Konfigurasi Gemini ===
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.critical(f"Gagal konfigurasi Gemini: {e}")

# === Load data kampus ===
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    now = datetime.now()
    TRISAKTI["current_context"]["date"] = now.strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = now.strftime("%H:%M WIB")
except Exception as e:
    logger.critical(f"Gagal load JSON kampus: {e}")
    TRISAKTI = {}

# === SymSpell ===
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1):
    logger.warning("Gagal memuat kamus SymSpell.")

# === Fungsi Bantuan ===

def detect_language(text):
    try:
        return detect(text) if len(text.strip().split()) > 1 else "id"
    except:
        return "id"

def correct_typo(text):
    corrected = []
    for word in text.split():
        s = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected.append(s[0].term if s else word)
    return " ".join(corrected)

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    return re.sub(r"(https?://[^\s<>'\"()]+)", r"<a href='\1' target='_blank' rel='noopener noreferrer'>🔗 Klik di sini</a>", text)

def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = []
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                history = json.load(f)
        history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "ai": ai_msg
        })
        with open(file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal menyimpan chat: {e}")

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
                wave_name = wave.get("wave")
                period = wave.get("period", "")
                start_str, end_str = [s.strip() for s in period.split(" - ")]
                start = parse_date(start_str, dayfirst=True).date()
                end = parse_date(end_str, dayfirst=True).date()

                if today < start:
                    status = f"{wave_name} ({jalur['name']}) akan dibuka mulai {start.strftime('%d %B %Y')}."
                elif start <= today <= end:
                    status = f"{wave_name} ({jalur['name']}) sedang berlangsung hingga {end.strftime('%d %B %Y')}."
                else:
                    status = f"{wave_name} ({jalur['name']}) sudah ditutup pada {end.strftime('%d %B %Y')}."

                summary.append(status)
        return "\n".join(summary)
    except Exception as e:
        logger.warning(f"Gagal menghitung status gelombang: {e}")
        return "Status pendaftaran tidak dapat ditentukan saat ini."

# === ROUTES ===

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    if "conversation" not in session:
        session["conversation"] = []
    session["conversation"].append({"user": corrected})
    session["conversation"] = session["conversation"][-50:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})
    registration_status_summary = get_current_registration_status()

    # === Jika permintaan brosur
    if kategori == "brosur":
        base_url = request.host_url.replace("http://", "https://").rstrip("/")
        brosur_url = f"{base_url}/download-brosur"
        reply = (
            "📄 Brosur resmi TMM siap diunduh!<br><br>"
            f"<a href='{brosur_url}' class='download-btn' target='_blank'>⬇️ Klik di sini untuk mengunduh brosur</a><br><br>"
            "Jika tidak bisa dibuka, salin link dan buka manual."
        )
        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang, "corrected": corrected if corrected != message else None})

    # === Prompt untuk Gemini
    system_prompt = (
        "Kamu adalah TIMU, asisten AI interaktif dari Trisakti School of Multimedia. "
        "Jawab dengan ramah, tidak terlalu panjang, tidak terlalu singkat, langsung ke poin. "
        "Kuasai semua bahasa dan jawablah berdasarkan data di bawah ini:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Status pendaftaran saat ini:\n{registration_status_summary}\n\n"
        f"Riwayat percakapan:\n{json.dumps(session['conversation'], ensure_ascii=False)}"
    )

    prompt = (
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Pertanyaan pengguna: \"{corrected}\"\n"
        f"Bahasa: {lang.upper()}\n"
        "Jawaban harus responsif, sopan, dan interaktif."
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={
            "temperature": 0.3,
            "top_p": 0.9,
            "max_output_tokens": 1024
        })
        result = model.generate_content(system_prompt + "\n\n" + prompt)
        raw = result.text.strip()
        reply = clean_response(raw).replace("TSM", "TMM")
        reply = format_links(reply)

        if not reply:
            reply = f"Maaf, saya belum punya informasi itu. Silakan hubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."

        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang, "corrected": corrected if corrected != message else None})
    
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal."}), 500
    except Exception as e:
        logger.error(f"[Internal Error] {e}")
        return jsonify({"error": "Kesalahan sistem."}), 500

@app.route("/download-brosur")
def download_brosur():
    try:
        file_path = os.path.join("static", "brosur_tmm.pdf")
        if not os.path.exists(file_path):
            return jsonify({"error": "Brosur tidak ditemukan."}), 404
        return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": "Gagal mengunduh brosur."}), 500

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
        "latest": history[-5:] if len(history) >= 5 else history
    })

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

# === Start Flask ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=bool(os.getenv("DEBUG", False)))