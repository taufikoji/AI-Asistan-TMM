import os, json, logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from langdetect import detect
import google.generativeai as genai
from symspellpy.symspellpy import SymSpell, Verbosity
from dateutil.parser import parse as parse_date

# Logging setup
logging.basicConfig(level=logging.INFO, filename='app.log', format='%(asctime)s - %(levelname)s - %(message)s')

# Load .env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret")
CORS(app)

# Gemini Config
genai.configure(api_key=GEMINI_API_KEY)

# Load JSON Data
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    TRISAKTI["current_context"] = {
        "date": datetime.now().strftime("%d %B %Y"),
        "time": datetime.now().strftime("%H:%M WIB")
    }
except Exception as e:
    logging.critical(f"Gagal load JSON: {e}")
    TRISAKTI = {}

# SymSpell init
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1):
    logging.warning("Gagal load dictionary SymSpell")

# === Utility ===
def detect_language(text):
    try:
        return detect(text) if len(text.split()) > 1 else "id"
    except: return "id"

def correct_typo(text):
    result = []
    for word in text.split():
        suggestions = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        result.append(suggestions[0].term if suggestions else word)
    return " ".join(result)

def clean_response(text):
    import re
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    import re
    return re.sub(r"(https?://[^\s<>'\"()]+)", r"<a href='\1' target='_blank'>🔗 Klik di sini</a>", text)

def save_chat(user_msg, ai_msg):
    try:
        history = json.load(open("chat_history.json", "r", encoding="utf-8")) if os.path.exists("chat_history.json") else []
        history.append({
            "timestamp": datetime.now().isoformat(),
            "user": user_msg,
            "ai": ai_msg
        })
        json.dump(history, open("chat_history.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"Gagal menyimpan chat: {e}")

def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return "general"

def get_current_registration_status():
    try:
        today = datetime.now().date()
        output = []
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
                output.append(status)
        return "\n".join(output)
    except Exception as e:
        logging.warning(f"Gagal hitung status pendaftaran: {e}")
        return "Status pendaftaran tidak tersedia saat ini."

# === Routes ===

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/chatroom")
def chatroom():
    return render_template("chatroom.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_stats"))
        return render_template("login.html", error="Password salah.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("landing"))

@app.route("/admin/stats")
def admin_stats():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))
    try:
        history = json.load(open("chat_history.json", "r", encoding="utf-8"))
    except:
        history = []
    return render_template("stats.html", stats={
        "total_chats": len(history),
        "latest": history[-5:]
    })

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
    session['conversation'] = session['conversation'][-20:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})
    registration_summary = get_current_registration_status()

    if kategori == "brosur":
        brosur_url = request.host_url.rstrip("/") + "/download-brosur"
        reply = (
            "📄 Brosur resmi TMM siap diunduh:<br><br>"
            f"<a href='{brosur_url}' class='download-btn' target='_blank'>⬇️ Klik di sini untuk mengunduh brosur</a>"
        )
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })

    # === Prompt AI ===
    system_prompt = (
        "Kamu adalah TIMU, asisten AI dari Trisakti School of Multimedia. "
        "Jawab cerdas, ringkas, santai, tidak terlalu formal, dan langsung ke inti.\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Status pendaftaran terkini:\n{registration_summary}\n\n"
        f"Riwayat singkat:\n{json.dumps(session['conversation'], ensure_ascii=False)}"
    )

    prompt = (
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Pertanyaan: \"{corrected}\"\n"
        f"Bahasa: {lang.upper()}\n"
        "Jawaban harus informatif dan bantu pengguna lanjut bertanya."
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
            reply = f"Maaf, saya belum tahu jawabannya. Silakan hubungi admin {TRISAKTI['institution']['contact']['whatsapp']}"
        save_chat(corrected, reply)
        return jsonify({
            "reply": reply,
            "language": lang,
            "corrected": corrected if corrected != message else None
        })
    except Exception as e:
        logging.error(f"[AI ERROR] {e}")
        return jsonify({"error": "Koneksi ke AI gagal"}), 500

@app.route("/download-brosur")
def download_brosur():
    path = os.path.join("static", "brosur_tmm.pdf")
    if os.path.exists(path):
        return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)
    return jsonify({"error": "File brosur tidak tersedia."}), 404

# Run
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)