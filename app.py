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

# ===================== KONFIG =====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="app.log")
logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY tidak ditemukan di .env!")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret")
CORS(app)

genai.configure(api_key=GEMINI_API_KEY)

# ===================== LOAD JSON DATA =====================
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    now = datetime.now()
    TRISAKTI["current_context"]["date"] = now.strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = now.strftime("%H:%M WIB")
    logger.info("JSON kampus dimuat: %s", TRISAKTI.get("institution", {}).get("name", "Tanpa Nama"))
except Exception as e:
    logger.critical("Gagal load JSON kampus: %s", str(e))
    TRISAKTI = {"institution": {"contact": {"whatsapp": "+6287742997808"}}}

# ===================== SYMSPELL =====================
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1):
    logger.warning("Kamus SymSpell gagal dimuat.")
    def correct_typo(text): return text

# ===================== UTIL =====================
def detect_language(text):
    try:
        return detect(text) if len(text.strip().split()) > 1 else "id"
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
    seen_urls = set()
    def replace_link(match):
        url = match.group(0)
        if url not in seen_urls:
            seen_urls.add(url)
            return f"<a href='{url}' target='_blank' rel='noopener noreferrer'>🔗 Klik di sini</a>"
        return ""
    return re.sub(r"(https?://[^\s<>'\"()]+)", replace_link, text)

def save_chat(user_msg, ai_msg):
    try:
        file = "chat_history.json"
        history = json.load(open(file, encoding="utf-8")) if os.path.exists(file) else []
        history.append({"timestamp": datetime.now().isoformat(), "user": user_msg, "ai": ai_msg})
        json.dump(history, open(file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Gagal menyimpan chat: %s", str(e))

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
                period = wave.get("period", "")
                if " - " not in period:
                    continue
                start_str, end_str = [s.strip() for s in period.split(" - ")]
                try:
                    start = parse_date(start_str, dayfirst=True).date()
                    end = parse_date(end_str, dayfirst=True).date()
                except Exception as e:
                    continue
                wave_name = wave.get("wave", "Gelombang")
                if today < start:
                    status = f"{wave_name} ({jalur['name']}) akan dibuka mulai {start.strftime('%d %B %Y')}."
                elif start <= today <= end:
                    status = f"{wave_name} ({jalur['name']}) sedang berlangsung hingga {end.strftime('%d %B %Y')}."
                else:
                    status = f"{wave_name} ({jalur['name']}) sudah ditutup pada {end.strftime('%d %B %Y')}."
                summary.append(status)
        return "\n".join(summary) if summary else "Belum ada informasi pendaftaran."
    except Exception as e:
        return "Status pendaftaran tidak tersedia."

def find_program_by_alias(query):
    query = query.lower()
    for program in TRISAKTI.get("academic_programs", []):
        for alias in program.get("aliases", []):
            if query in alias.lower() or alias.lower() in query:
                return program
    return None

# ===================== ROUTES =====================
@app.route("/")
def landing():
    session.clear()  # bersihkan riwayat saat reload
    return render_template("landing.html")

@app.route("/chat")
def chatroom():
    session.clear()  # reset obrolan saat reload
    return render_template("chatroom.html")

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
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

@app.route("/download-brosur")
def download_brosur():
    file_path = os.path.join("static", "brosur_tmm.pdf")
    if not os.path.exists(file_path):
        return jsonify({"error": "Brosur tidak tersedia."}), 404
    return send_from_directory("static", "brosur_tmm.pdf", as_attachment=True)

@app.route("/api/chat", methods=["GET", "POST"])
def chat():
    if request.method == "GET" and request.args.get("init"):
        return jsonify({"conversation": session.get('conversation', [])})

    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Pesan tidak ditemukan.", "conversation": session.get('conversation', [])}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"error": "Pesan kosong.", "conversation": session.get('conversation', [])}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    if 'conversation' not in session:
        session['conversation'] = []
    session['conversation'].append({"role": "user", "content": corrected})
    session['conversation'] = session['conversation'][-50:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})
    registration_status_summary = get_current_registration_status()

    if kategori == "brosur":
        base_url = request.host_url.replace("http://", "https://", 1).rstrip("/")
        brosur_url = f"{base_url}/download-brosur"
        reply = (
            "📄 Brosur resmi TMM siap diunduh!<br><br>"
            f"<a href='{brosur_url}' target='_blank'>⬇️ Unduh Brosur</a><br><br>"
            "Jika tidak bisa dibuka, salin link dan buka secara manual."
        )
        session['conversation'].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang, "conversation": session['conversation']})

    matched_program = find_program_by_alias(corrected)
    if matched_program:
        reply = (
            f"Program **{matched_program['name']}** adalah jurusan yang {matched_program['description'].lower()}<br><br>"
            f"📚 Spesialisasi: {', '.join(matched_program['specializations'])}<br>"
            f"🎓 Prospek Karier: {', '.join(matched_program['career_prospects'])}<br>"
            f"🏫 Akreditasi: {matched_program['accreditation']}<br>"
            f"{'🕓 Tersedia kelas malam.' if matched_program['evening_class'] else 'Tidak tersedia kelas malam.'}"
        )
        session['conversation'].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang, "conversation": session['conversation']})

    # 💬 PROMPT AI (versi optimal)
    short_history = session.get("conversation", [])[-6:]
    system_prompt = (
        "Kamu adalah TIMU, asisten AI dari Trisakti School of Multimedia (TMM). "
        "Tugasmu adalah menjawab berbagai pertanyaan tentang kampus, jurusan, beasiswa, pendaftaran, dan info lainnya dengan ramah, sopan, dan mudah dimengerti. "
        "Jika pengguna menggunakan bahasa daerah (Jawa, Sunda, Minang, dll), kamu bisa menyesuaikan gaya bahasanya. "
        "Kamu boleh sedikit bercanda atau menyelipkan motivasi, tetapi tetap profesional. "
        "Jangan ulangi sapaan seperti 'Halo' kecuali di awal sekali. Fokus langsung pada isi pertanyaan, bukan formalitas.\n\n"
        f"📌 Data Kampus:\n{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"📆 Status Pendaftaran Saat Ini:\n{registration_status_summary}\n\n"
        f"🗂️ Riwayat Obrolan Sebelumnya:\n{json.dumps(short_history, ensure_ascii=False)}"
    )

    prompt = (
        f"Tanggal: {context.get('date')}, Jam: {context.get('time')}\n"
        f"Pertanyaan pengguna: \"{corrected}\"\n"
        f"Bahasa terdeteksi: {lang.upper()}\n"
        "Jawaban harus natural, langsung ke inti, dan mudah dipahami."
    )

    try:
        model = genai.GenerativeModel("gemini-1.5-flash", generation_config={
            "temperature": 0.3, "top_p": 0.9, "max_output_tokens": 1024
        })
        result = model.generate_content(system_prompt + "\n\n" + prompt)
        reply = clean_response(result.text.strip()).replace("TSM", "TMM")
        reply = format_links(reply)

        if not reply.strip():
            reply = f"Maaf, saya belum punya info untuk itu. Hubungi WA {TRISAKTI['institution']['contact'].get('whatsapp')}."

        session['conversation'].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply, "language": lang, "conversation": session['conversation']})

    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini error: %s", str(e))
        return jsonify({"error": "Koneksi AI gagal, coba lagi nanti.", "conversation": session['conversation']}), 500
    except Exception as e:
        logger.error("Internal Error: %s", str(e))
        return jsonify({"error": "Kesalahan sistem.", "conversation": session['conversation']}), 500

# ===================== RUN =====================
if __name__ == "__main__":
    logger.info("Server dijalankan pada %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S WIB"))
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=True)