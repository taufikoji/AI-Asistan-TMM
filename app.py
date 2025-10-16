Ya. Ini aku berikan app full milikku. Lalu kamu perbarui dan berikan kembali kepada secara full agar fungsi fungsi yang lain tetap berfungsi: import os
import json
import logging
import re
from datetime import datetime
from dateutil.parser import parse as parse_date
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
from google import genai
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity
from google.api_core import exceptions as google_exceptions

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="app.log")
logger = logging.getLogger(__name__)

# -------------------- Load env --------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("❌ GEMINI_API_KEY tidak ditemukan di environment variable!")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FLASK_SECRET = os.getenv("FLASK_SECRET_KEY", "timu-secret-key")

# -------------------- Flask init --------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = FLASK_SECRET
CORS(app)

# -------------------- Gemini client --------------------
client = genai.Client(api_key=GEMINI_API_KEY)

# -------------------- Load JSON data --------------------
JSON_PATH = os.path.join(os.path.dirname(__file__), "trisakti_info.json")
try:
    with open(JSON_PATH, "r", encoding="utf-8") as jf:
        TRISAKTI = json.load(jf)
    now = datetime.now()
    TRISAKTI.setdefault("current_context", {})
    TRISAKTI["current_context"]["date"] = TRISAKTI["current_context"].get("date") or now.strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = TRISAKTI["current_context"].get("time") or now.strftime("%H:%M WIB")
    logger.info("✅ trisakti_info.json dimuat: %s", TRISAKTI.get("institution", {}).get("name"))
except Exception as e:
    logger.critical("Gagal memuat trisakti_info.json: %s", str(e))
    TRISAKTI = {
        "institution": {"contact": {"whatsapp": "+6287742997808", "instagram": "https://www.instagram.com/tmm_trisakti"}}
    }

# -------------------- SymSpell (typo correction) --------------------
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
DICT_PATH = os.path.join(os.path.dirname(__file__), "indonesia_dictionary_3000.txt")
if not symspell.load_dictionary(DICT_PATH, 0, 1):
    logger.warning("⚠️ Kamus SymSpell gagal dimuat. Koreksi typo dinonaktifkan.")
    def correct_typo(text): return text

def correct_typo(text):
    corrected = []
    for word in text.split():
        suggestions = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected.append(suggestions[0].term if suggestions else word)
    return " ".join(corrected)

# -------------------- Utilities --------------------
def detect_language(text):
    try:
        return detect(text) if len(text.strip().split()) > 1 else "id"
    except:
        return "id"

def clean_response(text):
    return re.sub(r"[*_`]+", "", text)

def format_links(text):
    """
    Deteksi URL dalam teks dan ubah jadi <a href> HTML.
    Hindari duplikat dan jangan ubah link yang sudah dalam format HTML.
    """
    if not text:
        return text

    seen = set()

    # Abaikan link yang sudah dikonversi ke HTML <a href="...">
    def repl(match):
        url = match.group(0)
        # Lewati jika sudah berupa HTML <a href=...>
        if re.search(r"<a\s+href=", url, flags=re.I):
            return url

        # Normalisasi URL untuk mencegah duplikasi
        normalized = url.strip().rstrip("/").lower()
        if normalized in seen:
            return ""
        seen.add(normalized)

        # Buat tautan aman
        return f"<a href='{url}' target='_blank' rel='noopener noreferrer'>🔗 {url}</a>"

    # Regex tangkap URL tapi abaikan yang sudah dalam tag <a>
    pattern = r"(?<!href=['\"])(https?://[^\s<>'\"()]+)"
    formatted = re.sub(pattern, repl, text)

    # Hapus spasi ganda akibat penghapusan duplikat
    formatted = re.sub(r"\s{2,}", " ", formatted).strip()
    return formatted

def save_chat(user_msg, ai_msg):
    try:
        fname = os.path.join(os.path.dirname(__file__), "chat_history.json")
        history = json.load(open(fname, encoding="utf-8")) if os.path.exists(fname) else []
        history.append({"timestamp": datetime.now().isoformat(), "user": user_msg, "ai": ai_msg})
        json.dump(history, open(fname, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Gagal menyimpan chat: %s", str(e))

def get_category(msg):
    msg = msg.lower()
    for cat, keys in TRISAKTI.get("keywords", {}).items():
        for k in keys:
            if k in msg:
                return cat
    return "general"

def get_current_registration_status():
    try:
        today = datetime.now().date()
        out = []
        for p in TRISAKTI.get("registration", {}).get("paths", []):
            for w in p.get("waves", []):
                period = w.get("period", "")
                if " - " not in period:
                    continue
                start_str, end_str = [s.strip() for s in period.split(" - ")]
                try:
                    start = parse_date(start_str, dayfirst=True).date()
                    end = parse_date(end_str, dayfirst=True).date()
                except:
                    continue
                wave_name = w.get("wave", "Gelombang")
                if today < start:
                    out.append(f"{wave_name} ({p.get('name')}) akan dibuka {start.strftime('%d %B %Y')}.")
                elif start <= today <= end:
                    out.append(f"{wave_name} ({p.get('name')}) sedang berlangsung hingga {end.strftime('%d %B %Y')}.")
                else:
                    out.append(f"{wave_name} ({p.get('name')}) sudah ditutup {end.strftime('%d %B %Y')}.")
        return "\n".join(out) if out else "Belum ada informasi pendaftaran."
    except Exception as e:
        logger.warning("Gagal menentukan status pendaftaran: %s", e)
        return "Status pendaftaran tidak tersedia."

def find_program_by_alias(query):
    q = query.lower()
    for prog in TRISAKTI.get("academic_programs", []):
        for a in prog.get("aliases", []):
            if a.lower() in q or q in a.lower():
                return prog
        specs = prog.get("specializations", [])
        if isinstance(specs, list):
            for s in specs:
                if isinstance(s, dict):
                    title = s.get("title", "").lower()
                    if title and (title in q or q in title):
                        clone = {
                            "name": prog["name"],
                            "description": prog.get("description", ""),
                            "specializations": [sp.get("title") if isinstance(sp, dict) else sp for sp in (prog.get("specializations") or [])],
                            "career_prospects": s.get("career_prospects") if s.get("career_prospects") else prog.get("career_prospects", []),
                            "accreditation": s.get("accreditation", prog.get("accreditation", "BAIK")),
                            "evening_class": s.get("evening_class", prog.get("evening_class", False))
                        }
                        return clone
    return None

# -------------------- Routes --------------------
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
        with open(os.path.join(os.path.dirname(__file__), "chat_history.json"), "r", encoding="utf-8") as f:
            history = json.load(f)
    except:
        history = []
    return render_template("stats.html", stats={"total_chats": len(history), "latest": history[-5:] if len(history)>=5 else history})

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

@app.route("/download-brosur")
def download_brosur():
    path = os.path.join(app.static_folder, "brosur_tmm.pdf")
    if not os.path.exists(path):
        return jsonify({"error": "Brosur tidak tersedia."}), 404
    return send_from_directory(app.static_folder, "brosur_tmm.pdf", as_attachment=True)

@app.route("/api/clear-session", methods=["POST"])
def clear_session():
    session.pop("conversation", None)
    return jsonify({"ok": True})

@app.route("/api/chat", methods=["POST"])
def api_chat():
    payload = request.get_json()
    if not payload or "message" not in payload:
        return jsonify({"error": "Pesan tidak ditemukan."}), 400
    message = payload["message"].strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    lang = detect_language(message)
    corrected = correct_typo(message)

    session.setdefault("conversation", [])
    session["conversation"].append({"role": "user", "content": corrected})
    session["conversation"] = session["conversation"][-50:]

    category = get_category(corrected)
    reg_status = get_current_registration_status()

    if category == "brosur":
        brosur_url = url_for("download_brosur", _external=True)
        reply = f"📄 Brosur resmi TMM siap diunduh:<br><a href='{brosur_url}' target='_blank'>⬇️ Unduh Brosur</a>"
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

    if category in ("pendaftaran", "registration"):
        links = []
        for p in TRISAKTI.get("registration", {}).get("paths", []):
            l = p.get("link")
            if l and l not in links:
                links.append(l)
        links_html = "<br>".join([f"<a href='{l}' target='_blank'>{l}</a>" for l in links]) if links else TRISAKTI.get("registration", {}).get("link", "")
        reply = f"📝 Link pendaftaran resmi:<br>{links_html}<br><br>{reg_status}"
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

    program = find_program_by_alias(corrected)
    if program:
        specs = program.get("specializations") or []
        if specs and isinstance(specs[0], dict):
            specs_list = [s.get("title") for s in specs]
        else:
            specs_list = specs
        career = program.get("career_prospects") or []
        accreditation = program.get("accreditation", "BAIK")
        evening_class = program.get("evening_class", False)
        evening_class_note = program.get("evening_class", False)
        reply = (
            f"🎓 <b>{program.get('name')}</b><br>"
            f"{program.get('description', '')}<br><br>"
            f"📚 Spesialisasi: {', '.join(specs_list) if specs_list else 'Tidak tersedia'}<br>"
            f"🎯 Prospek Karier: {', '.join(career) if career else 'Tidak tersedia'}<br>"
            f"🏫 Akreditasi: {accreditation}<br>"
            f"{'🕓 Tersedia kelas malam (Alih Jenjang/AJ).' if evening_class else 'Tidak Tersedia Kelas Malam.'}"
        )
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        return jsonify({"reply": reply})

    short_history = session.get("conversation", [])[-6:]
    system_prompt = (
        "Kamu adalah TIMU, asisten AI Trisakti School of Multimedia (TMM). "
        "kamu harus ramah dan dapat berinteraksi dengan baik"
        "kamu harus ekspresif dan dapat di ajak bercanda ringan"
        "kamu ahli dalam berbagai bahasa apapun namun bahasa utama kamu mengikuti bahasa pengguna"
        "Jawablah dengan sopan dan ringkas dalam bahasa pengguna. Gunakan data institusi berikut jika relevan:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\nStatus Pendaftaran:\n{reg_status}\n\n"
        f"Riwayat Singkat:\n{json.dumps(short_history, ensure_ascii=False)}"
    )
    user_prompt = (
        f"Tanggal: {TRISAKTI.get('current_context', {}).get('date')} | Jam: {TRISAKTI.get('current_context', {}).get('time')}\n"
        f"Pertanyaan: {corrected}\nBahasa: {lang.upper()}\nJawablah singkat, informatif, dan mudah dipahami."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt + "\n\n" + user_prompt
        )
        reply_text = clean_response(response.text.strip())
        reply_text = format_links(reply_text)

        if not reply_text or re.search(r"\b(maaf|tidak tahu|belum)\b", reply_text, flags=re.I):
            kontak = TRISAKTI.get("institution", {}).get("contact", {})
            wa = kontak.get("whatsapp")
            ig = kontak.get("instagram")
            reply_text = (
                "Maaf, saya belum punya info lengkap untuk pertanyaan tersebut.<br>"
                f"Silakan hubungi petugas kami:<br>"
                f"📱 WhatsApp: <a href='https://wa.me/{wa.replace('+','')}' target='_blank'>{wa}</a><br>"
                f"📸 Instagram: <a href='{ig}' target='_blank'>{ig}</a>"
            )

        session["conversation"].append({"role": "bot", "content": reply_text})
        save_chat(corrected, reply_text)
        return jsonify({"reply": reply_text})

    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini API Error: %s", e)
        kontak = TRISAKTI.get("institution", {}).get("contact", {})
        wa = kontak.get("whatsapp")
        ig = kontak.get("instagram")
        reply_text = (
            "Koneksi AI gagal. Silakan hubungi petugas kami di:<br>"
            f"📱 WhatsApp: <a href='https://wa.me/{wa.replace('+','')}' target='_blank'>{wa}</a><br>"
            f"📸 Instagram: <a href='{ig}' target='_blank'>{ig}</a>"
        )
        return jsonify({"reply": reply_text}), 500
    except Exception as e:
        logger.error("Internal Error: %s", e)
        return jsonify({"error": "Kesalahan sistem internal."}), 500

# -------------------- Run --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info("🚀 TIMU berjalan di port %s", port)
    app.run(host="0.0.0.0", port=port)