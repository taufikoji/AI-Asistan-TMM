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
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="app.log")
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret")
CORS(app)

# Konfigurasi Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Load data kampus
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
if not symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1):
    logger.warning("Gagal memuat kamus SymSpell.")

# Fungsi bantu
def detect_language(text):
    try:
        if len(text.strip().split()) <= 1:
            return "id"
        return detect(text)
    except:
        return "id"

def correct_typo(text):
    corrected = []
    for word in text.split():
        suggestions = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected.append(suggestions[0].term if suggestions else word)
    return " ".join(corrected)

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    return re.sub(r"(https?://[^\s<>'\"()]+)", r"<a href='\1' target='_blank' rel='noopener noreferrer'>🔗 Klik di sini</a>", text)

def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = json.load(open(file, encoding="utf-8")) if os.path.exists(file) else []
        history.append({"timestamp": datetime.now().isoformat(), "user": user_msg, "ai": ai_msg})
        json.dump(history, open(file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal menyimpan chat: {e}")

def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

def get_current_gelombang(info):
    try:
        today = datetime.today().date()
        gelombang_aktif = None
        semua_gelombang = info.get("pendaftaran", {}).get("gelombang", [])

        for g in semua_gelombang:
            mulai = datetime.strptime(g["mulai"], "%Y-%m-%d").date()
            selesai = datetime.strptime(g["selesai"], "%Y-%m-%d").date()
            if mulai <= today <= selesai:
                gelombang_aktif = {
                    "status": "berlangsung",
                    "nama": g["nama"],
                    "mulai": mulai.strftime("%d %B %Y"),
                    "selesai": selesai.strftime("%d %B %Y")
                }
                break
            elif today < mulai:
                gelombang_aktif = {
                    "status": "akan datang",
                    "nama": g["nama"],
                    "mulai": mulai.strftime("%d %B %Y"),
                    "selesai": selesai.strftime("%d %B %Y")
                }
                break

        if not gelombang_aktif and semua_gelombang:
            gelombang_aktif = {
                "status": "selesai",
                "nama": semua_gelombang[-1]["nama"],
                "selesai": datetime.strptime(semua_gelombang[-1]["selesai"], "%Y-%m-%d").strftime("%d %B %Y")
            }

        return gelombang_aktif
    except Exception as e:
        logger.error(f"Gagal menentukan gelombang: {e}")
        return None

# ==== ROUTES ====

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

    if 'conversation' not in session:
        session['conversation'] = []
    session['conversation'].append({"user": corrected})
    session['conversation'] = session['conversation'][-55:]  # simpan 55 terakhir

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})
    context["gelombang_aktif"] = get_current_gelombang(TRISAKTI)

    if kategori == "brosur":
        base_url = request.host_url.replace("http://", "https://", 1).rstrip("/")
        brosur_url = f"{base_url}/download-brosur"
        reply = (
            "📄 Brosur resmi TMM siap diunduh!<br><br>"
            f"<a href='{brosur_url}' class='download-btn' target='_blank'>⬇️ Klik di sini untuk mengunduh brosur</a><br><br>"
            "Jika tidak bisa dibuka, salin link dan buka manual."
        )
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    # ==== PROMPT FINAL ====
    system_prompt = (
        "Kamu adalah TIMU, asisten AI resmi Trisakti School of Multimedia. "
        "Jawab langsung ke poin, tidak perlu menyapa. Jangan terlalu singkat atau terlalu panjang. Gunakan data berikut jika relevan:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Status gelombang saat ini:\n{json.dumps(context.get('gelombang_aktif', {}), ensure_ascii=False)}\n\n"
        f"Riwayat singkat percakapan:\n{json.dumps(session['conversation'], ensure_ascii=False)}"
    )

    prompt = (
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Pertanyaan pengguna: \"{corrected}\"\n"
        f"Bahasa: {lang.upper()}\n"
        "Jawaban harus kontekstual, jelas, dan bantu pengguna jika mereka ingin bertanya lebih lanjut."
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={
            "temperature": 0.3, "top_p": 0.9, "max_output_tokens": 1024
        })
        result = model.generate_content(system_prompt + "\n\n" + prompt)
        raw = result.text.strip()
        reply = clean_response(raw).replace("TSM", "TMM")
        reply = format_links(reply)

        if not reply:
            reply = f"Maaf, saya belum punya informasi itu. Silakan hubungi WhatsApp {TRISAKTI['institution']['contact']['whatsapp']}."

        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"[Gemini API Error] {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"[Internal Error] {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

@app.route("/download-brosur")
def download_brosur():
    try:
        file_path = os.path.join("static", "brosur_tmm.pdf")
        if not os.path.exists(file_path):
            return jsonify({"error": "Brosur tidak tersedia."}), 404
        return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)
    except Exception as e:
        logger.error(f"Error download brosur: {e}")
        return jsonify({"error": "Gagal unduh brosur."}), 500

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

# ==== RUN ====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)