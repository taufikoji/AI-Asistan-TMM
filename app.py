import os
import json
import logging
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
from dateutil.parser import parse as parse_date
from google import genai
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity
from google.api_core import exceptions as google_exceptions

# ===================== KONFIGURASI DASAR =====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="app.log")
logger = logging.getLogger(__name__)

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("❌ GEMINI_API_KEY tidak ditemukan di environment variable!")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "timu-secret-key")
CORS(app)

# ===================== KONFIGURASI GEMINI =====================
client = genai.Client(api_key=GEMINI_API_KEY)

# ===================== LOAD DATA JSON =====================
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
    now = datetime.now()
    TRISAKTI["current_context"]["date"] = now.strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = now.strftime("%H:%M WIB")
    logger.info("✅ JSON kampus dimuat: %s", TRISAKTI.get("institution", {}).get("name", "Tanpa Nama"))
except Exception as e:
    logger.critical("Gagal memuat JSON kampus: %s", str(e))
    TRISAKTI = {"institution": {"contact": {"whatsapp": "+6287742997808"}}}

# ===================== SYMSPELL =====================
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
if not symspell.load_dictionary("indonesia_dictionary_3000.txt", 0, 1):
    logger.warning("⚠️ Kamus SymSpell gagal dimuat. Koreksi typo dinonaktifkan.")
    def correct_typo(text): return text

def correct_typo(text):
    corrected = []
    for word in text.split():
        suggestions = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected.append(suggestions[0].term if suggestions else word)
    return " ".join(corrected)

# ===================== UTILITAS =====================
def detect_language(text):
    try:
        return detect(text) if len(text.strip().split()) > 1 else "id"
    except:
        return "id"

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    seen = set()
    def repl(m):
        url = m.group(0)
        if url not in seen:
            seen.add(url)
            return f"<a href='{url}' target='_blank' rel='noopener noreferrer'>🔗 Klik di sini</a>"
        return ""
    return re.sub(r"(https?://[^\s<>'\"()]+)", repl, text)

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
    for cat, keys in TRISAKTI.get("keywords", {}).items():
        if any(k in msg for k in keys):
            return cat
    return "general"

def get_current_registration_status():
    try:
        today = datetime.now().date()
        summary = []
        for path in TRISAKTI.get("registration", {}).get("paths", []):
            for wave in path.get("waves", []):
                period = wave.get("period", "")
                if " - " not in period:
                    continue
                start_str, end_str = [s.strip() for s in period.split(" - ")]
                try:
                    start = parse_date(start_str, dayfirst=True).date()
                    end = parse_date(end_str, dayfirst=True).date()
                except:
                    continue
                wave_name = wave.get("wave", "Gelombang")
                if today < start:
                    status = f"{wave_name} ({path['name']}) akan dibuka {start.strftime('%d %B %Y')}."
                elif start <= today <= end:
                    status = f"{wave_name} ({path['name']}) sedang berlangsung hingga {end.strftime('%d %B %Y')}."
                else:
                    status = f"{wave_name} ({path['name']}) sudah ditutup {end.strftime('%d %B %Y')}."
                summary.append(status)
        return "\n".join(summary) if summary else "Belum ada informasi pendaftaran."
    except:
        return "Status pendaftaran tidak tersedia."

def find_program_by_alias(query):
    query = query.lower()
    for prog in TRISAKTI.get("academic_programs", []):
        for alias in prog.get("aliases", []):
            if query in alias.lower() or alias.lower() in query:
                return prog
    return None

# ===================== WEB SCRAPING =====================
def scrape_website(query):
    try:
        url = TRISAKTI.get("institution", {}).get("website")
        if not url:
            return None
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        # Cari teks yang relevan
        for p in soup.find_all(["p","li"]):
            text = p.get_text().strip()
            if query.lower() in text.lower():
                return text
        return None
    except Exception as e:
        logger.warning("Web scraping error: %s", str(e))
        return None

# ===================== ROUTES =====================
@app.route("/")
def landing():
    session.clear()
    return render_template("landing.html")

@app.route("/chat")
def chatroom():
    session.clear()
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

# ===================== API CHAT =====================
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Pesan tidak ditemukan."}), 400

    message = data["message"].strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    if "conversation" not in session:
        session["conversation"] = []
    session["conversation"].append({"role": "user", "content": corrected})
    session["conversation"] = session["conversation"][-50:]

    kategori = get_category(corrected)
    context = TRISAKTI.get("current_context", {})
    registration_summary = get_current_registration_status()

    # ================= JSON CHECK =================
    if kategori == "brosur":
        base_url = request.host_url.rstrip("/")
        brosur_url = f"{base_url}/download-brosur"
        reply = f"📄 Brosur resmi TMM siap diunduh!<br><a href='{brosur_url}' target='_blank'>⬇️ Unduh Brosur</a>"
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

    matched_program = find_program_by_alias(corrected)
    if matched_program:
        reply = (
            f"Program {matched_program['name']} adalah jurusan yang {matched_program['description'].lower()}<br>"
            f"📚 Spesialisasi: {', '.join(matched_program['specializations'])}<br>"
            f"🎓 Prospek Karier: {', '.join(matched_program['career_prospects'])}<br>"
            f"🏫 Akreditasi: {matched_program['accreditation']}<br>"
            f"{'🕓 Tersedia kelas malam.' if matched_program['evening_class'] else 'Tidak tersedia kelas malam.'}<br>"
            f"🔗 Info pendaftaran: <a href='{TRISAKTI['registration']['link']}' target='_blank'>Klik di sini</a>"
        )
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

    # ================= WEB SCRAPING =================
    scraped = scrape_website(corrected)
    if scraped:
        reply = f"Berikut info tambahan dari website resmi TMM:\n{scraped}\n\nJika perlu info lebih lengkap, silakan hubungi WA {TRISAKTI['institution']['contact'].get('whatsapp')} atau Instagram {TRISAKTI['institution']['contact']['social_media'].get('instagram')}."
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

    # ================= GEMINI FALLBACK =================
    short_history = session.get("conversation", [])[-6:]
    system_prompt = (
        "Kamu adalah TIMU, asisten AI dari Trisakti School of Multimedia (TMM). "
        "Jawablah sopan, natural, dan kontekstual. "
        "Gunakan data JSON sebagai referensi utama. "
        "Jika data tidak ada, berikan jawaban relevan namun tetap sarankan untuk menghubungi petugas via WA/IG."
    )
    user_prompt = f"Pertanyaan: {corrected}\nBahasa: {lang.upper()}\nRiwayat singkat: {json.dumps(short_history, ensure_ascii=False)}"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt + "\n\n" + user_prompt
        )
        reply = clean_response(response.text.strip()).replace("TSM", "TMM")
        reply += f"\n\n📱 Untuk info lebih lengkap, hubungi WA {TRISAKTI['institution']['contact'].get('whatsapp')} atau Instagram {TRISAKTI['institution']['contact']['social_media'].get('instagram')}."
        reply = format_links(reply)
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})
    except Exception as e:
        logger.error("Gemini fallback error: %s", str(e))
        reply = f"Maaf, saya belum bisa memberikan jawaban lengkap. Hubungi WA {TRISAKTI['institution']['contact'].get('whatsapp')} atau Instagram {TRISAKTI['institution']['contact']['social_media'].get('instagram')}."
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

# ===================== MAIN =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)