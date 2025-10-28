import os
import json
import logging
import re
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from flask import (
    Flask, request, jsonify, render_template,
    send_from_directory, session, redirect, url_for, abort
)
from dotenv import load_dotenv
from flask_cors import CORS
from google import genai
from langdetect import detect
from symspellpy.symspellpy import SymSpell, Verbosity
from google.api_core import exceptions as google_exceptions
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import bleach

# -------------------- Logging --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# -------------------- Load env --------------------
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("❌ GEMINI_API_KEY tidak ditemukan di environment variable!")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FLASK_SECRET = os.getenv("FLASK_SECRET_KEY", "timu-secret-key")

# Whitelist origin (untuk WordPress / domain resmi)
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://ai-asistan-tmm.onrender.com,https://trisaktimultimedia.ac.id,https://www.trisaktimultimedia.ac.id"
    ).split(",") if o.strip()
]

# -------------------- Flask init --------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = FLASK_SECRET

# Trust proxy dari Render/Reverse Proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Session & request hardening
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=16 * 1024,  # 16KB
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6),
    PREFERRED_URL_SCHEME="https",
)

# CORS whitelist
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# Rate limit per IP
limiter = Limiter(get_remote_address, app=app,
                  default_limits=["600 per hour", "60 per minute"])

# -------------------- Gemini client --------------------
client = genai.Client(api_key=GEMINI_API_KEY)

# -------------------- Load JSON data --------------------
JSON_PATH = os.path.join(os.path.dirname(__file__), "trisakti_info.json")
try:
    with open(JSON_PATH, "r", encoding="utf-8") as jf:
        TRISAKTI = json.load(jf)
    # pastikan Instagram username saja
    ig = TRISAKTI.get("institution", {}).get("contact", {}).get("instagram", "")
    if ig:
        ig = ig.split("/")[-1].strip("@")
        TRISAKTI["institution"]["contact"]["instagram"] = ig

    now = datetime.now()
    TRISAKTI.setdefault("current_context", {})
    TRISAKTI["current_context"]["date"] = TRISAKTI["current_context"].get("date") or now.strftime("%d %B %Y")
    TRISAKTI["current_context"]["time"] = TRISAKTI["current_context"].get("time") or now.strftime("%H:%M WIB")
    logger.info("✅ trisakti_info.json dimuat: %s", TRISAKTI.get("institution", {}).get("name"))
except Exception as e:
    logger.critical("Gagal memuat trisakti_info.json: %s", str(e))
    TRISAKTI = {
        "institution": {"contact": {"whatsapp": "+6287742997808", "instagram": "tmm_trisakti"}}
    }

# -------------------- SymSpell (typo correction) --------------------
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
DICT_PATH = os.path.join(os.path.dirname(__file__), "indonesia_dictionary_3000.txt")
_symspell_loaded = False
try:
    _symspell_loaded = symspell.load_dictionary(DICT_PATH, 0, 1)
except Exception as e:
    logger.warning("⚠️ Kamus SymSpell gagal dimuat: %s. Koreksi typo dinonaktifkan.", e)

def correct_typo(text: str) -> str:
    if not _symspell_loaded:
        return text
    corrected = []
    for word in text.split():
        suggestions = symspell.lookup(word, Verbosity.CLOSEST, max_edit_distance=2)
        corrected.append(suggestions[0].term if suggestions else word)
    return " ".join(corrected)

# -------------------- Utilities --------------------
def detect_language(text):
    try:
        return detect(text) if len(text.strip().split()) > 1 else "id"
    except Exception:
        return "id"

def clean_response(text):
    # Hanya hapus * dan `, jangan hapus underscore
    return re.sub(r"[*`]+", "", text or "")

def format_links(text):
    if not text:
        return text
    seen = set()
    def repl(match):
        url = match.group(0)
        if re.search(r"<a\s+href=", url, flags=re.I):
            return url
        normalized = url.strip().rstrip("/").lower()
        if normalized in seen:
            return ""
        seen.add(normalized)
        return f"<a href='{url}' target='_blank' rel='noopener noreferrer nofollow'>🔗 {url}</a>"
    pattern = r"(?<!href=['\"])(https?://[^\s<>'\"()]+)"
    formatted = re.sub(pattern, repl, text)
    formatted = re.sub(r"\s{2,}", " ", formatted).strip()
    return formatted

# Sanitasi HTML (XSS guard)
BLEACH_TAGS = ["a", "b", "strong", "em", "br"]
BLEACH_ATTRS = {"a": ["href", "target", "rel"]}
BLEACH_PROTOCOLS = ["http", "https"]
def sanitize_html(html_text: str) -> str:
    return bleach.clean(html_text or "", tags=BLEACH_TAGS, attributes=BLEACH_ATTRS,
                        protocols=BLEACH_PROTOCOLS, strip=True)

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
    for cat, keys in (TRISAKTI.get("keywords") or {}).items():
        for k in keys:
            if k in msg:
                return cat
    return "general"

# Cache sederhana untuk status pendaftaran (hemat hit)
_last_reg = {"t": None, "v": "Belum ada informasi pendaftaran."}
def get_current_registration_status():
    try:
        if _last_reg["t"] and (datetime.now() - _last_reg["t"]).seconds < 600:
            return _last_reg["v"]

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
                except Exception:
                    continue
                wave_name = w.get("wave", "Gelombang")
                if today < start:
                    out.append(f"{wave_name} ({p.get('name')}) akan dibuka {start.strftime('%d %B %Y')}.")
                elif start <= today <= end:
                    out.append(f"{wave_name} ({p.get('name')}) sedang berlangsung hingga {end.strftime('%d %B %Y')}.")
                else:
                    out.append(f"{wave_name} ({p.get('name')}) sudah ditutup {end.strftime('%d %B %Y')}.")
        val = "\n".join(out) if out else "Belum ada informasi pendaftaran."
        _last_reg["t"], _last_reg["v"] = datetime.now(), val
        return val
    except Exception as e:
        logger.warning("Gagal menentukan status pendaftaran: %s", e)
        return "Status pendaftaran tidak tersedia."

def _normalize_specs(specs):
    """Terima list of dict({'title':..}) atau list of string -> list of string."""
    if not isinstance(specs, list):
        return []
    out = []
    for s in specs:
        if isinstance(s, dict):
            t = s.get("title")
            if t:
                out.append(str(t))
        elif isinstance(s, str):
            out.append(s)
    return out

def find_program_by_alias(query):
    q = (query or "").lower()

    for prog in TRISAKTI.get("academic_programs", []):
        # 1) Cocokkan name langsung
        name = (prog.get("name") or "").lower()
        if name and (name in q or q in name):
            return prog

        # 2) Cocokkan alias
        for a in (prog.get("aliases") or []):
            if a and (a.lower() in q or q in a.lower()):
                return prog

        # 3) Cocokkan judul spesialisasi
        specs = prog.get("specializations", [])
        if isinstance(specs, list):
            for s in specs:
                title = (s.get("title") if isinstance(s, dict) else s) or ""
                title_l = title.lower()
                if title_l and (title_l in q or q in title_l):
                    clone = {
                        "name": prog.get("name"),
                        "description": prog.get("description", ""),
                        "specializations": _normalize_specs(prog.get("specializations")),
                        "career_prospects": (s.get("career_prospects") if isinstance(s, dict) else None) or prog.get("career_prospects", []),
                        "accreditation": (s.get("accreditation") if isinstance(s, dict) else None) or prog.get("accreditation", "BAIK"),
                        "evening_class": (s.get("evening_class") if isinstance(s, dict) else None) or prog.get("evening_class", False)
                    }
                    return clone
    return None

# -------------------- Origin/Referer check --------------------
def _is_allowed_origin(req) -> bool:
    origin = req.headers.get("Origin") or ""
    referer = req.headers.get("Referer") or ""
    if origin and any(origin.startswith(o) for o in ALLOWED_ORIGINS):
        return True
    if referer and any(referer.startswith(o) for o in ALLOWED_ORIGINS):
        return True
    # izinkan testing via Postman/curl jika ALLOW_TESTING=1
    return os.getenv("ALLOW_TESTING", "0") == "1"

def _precheck_request():
    if not _is_allowed_origin(request):
        abort(403)
    if request.content_length and request.content_length > 4 * 1024:  # 4KB
        abort(413)

# -------------------- Routes (UI) --------------------
@app.route("/")
@limiter.limit("30/minute")
def landing():
    session.clear()
    return render_template("landing.html")

# kamu pakai /chat untuk halaman chatroom — tetap dipertahankan
@app.route("/chat")
@limiter.limit("30/minute")
def chatroom():
    # jangan clear session di sini biar history tidak hilang saat refresh
    return render_template("chatroom.html")

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("20/minute")
def login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_stats"))
        return render_template("login.html", error="Password salah.")
    return render_template("login.html")

@app.route("/admin/stats")
@limiter.limit("10/minute")
def admin_stats():
    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))
    try:
        with open(os.path.join(os.path.dirname(__file__), "chat_history.json"), "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []
    return render_template("stats.html", stats={"total_chats": len(history), "latest": history[-5:] if len(history)>=5 else history})

@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("login"))

@app.route("/download-brosur")
@limiter.limit("30/minute")
def download_brosur():
    path = os.path.join(app.static_folder, "brosur_tmm.pdf")
    if not os.path.exists(path):
        return jsonify({"error": "Brosur tidak tersedia."}), 404
    return send_from_directory(app.static_folder, "brosur_tmm.pdf", as_attachment=True)

# -------------------- API --------------------
@app.route("/api/clear-session", methods=["POST"])
@limiter.limit("15/minute")
def clear_session():
    _precheck_request()
    session.pop("conversation", None)
    return jsonify({"ok": True})

# Endpoint lama kamu — tetap hidup
@app.route("/api/chat", methods=["POST"])
@limiter.limit("60/minute")
def api_chat():
    _precheck_request()
    return _chat_handler()

# Endpoint baru untuk widget WordPress: POST /chat
@app.route("/chat", methods=["POST"])
@limiter.limit("60/minute")
def chat_from_widget():
    _precheck_request()
    return _chat_handler()

# -------- Core handler: shared by /api/chat dan POST /chat --------
def _chat_handler():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400
    if len(message) > 1000:
        return jsonify({"error": "Pesan terlalu panjang (max 1000 karakter)."}), 413

    lang = detect_language(message)
    corrected = correct_typo(message)

    session.setdefault("conversation", [])
    session["conversation"].append({"role": "user", "content": corrected})
    session["conversation"] = session["conversation"][-50:]

    category = get_category(corrected)
    reg_status = get_current_registration_status()

    # Quick replies manusiawi untuk pesan pendek
    quick_replies = {
        "ga": "Oke 😊",
        "nggak": "Siap, nggak masalah kok 😄",
        "enggak": "Baiklah 😌",
        "iya": "Iya, siap! 🙌",
        "ok": "Oke 👍",
        "oke": "Siap~ 🚀",
        "wkwk": "Hehe 😆",
        "hmm": "Hmm, gimana kalau kamu jelasin dikit lagi?"
    }
    msg_lower = corrected.lower().strip()
    if msg_lower in quick_replies:
        reply = sanitize_html(quick_replies[msg_lower])
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Kategori khusus
    if category == "brosur":
        brosur_url = url_for("download_brosur", _external=True)
        reply = f"📄 Brosur resmi TMM siap diunduh:<br><a href='{brosur_url}' target='_blank' rel='noopener'>⬇️ Unduh Brosur</a>"
        reply = sanitize_html(reply)
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    if category in ("pendaftaran", "registration"):
        links = []
        for p in TRISAKTI.get("registration", {}).get("paths", []):
            l = p.get("link")
            if l and l not in links:
                links.append(l)
        links_html = "<br>".join([f"<a href='{l}' target='_blank' rel='noopener'>{l}</a>" for l in links]) if links else TRISAKTI.get("registration", {}).get("link", "")
        reply = f"📝 Link pendaftaran resmi:<br>{links_html}<br><br>{reg_status}"
        reply = sanitize_html(reply)
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Cek program studi
    program = find_program_by_alias(corrected)
    if program:
        specs_list = _normalize_specs(program.get("specializations"))
        career = program.get("career_prospects") or []
        accreditation = program.get("accreditation", "BAIK")
        evening_class = program.get("evening_class", False)
        reply = (
            f"🎓 <b>{program.get('name')}</b><br>"
            f"{program.get('description', '')}<br><br>"
            f"📚 Spesialisasi: {', '.join(specs_list) if specs_list else 'Tidak tersedia'}<br>"
            f"🎯 Prospek Karier: {', '.join(career) if career else 'Tidak tersedia'}<br>"
            f"🏫 Akreditasi: {accreditation}<br>"
            f"{'🕓 Tersedia kelas malam (Alih Jenjang/AJ).' if evening_class else 'Tidak Tersedia Kelas Malam.'}"
        )
        reply = sanitize_html(reply)
        session["conversation"].append({"role": "bot", "content": reply})
        save_chat(corrected, reply)
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Chat AI umum (persona manusiawi & multilingual ringan)
    short_history = session.get("conversation", [])[-6:]
    system_prompt = (
        "Kamu adalah TIMU, asisten dari Trisakti School of Multimedia (TMM) yang berbicara seperti manusia muda: "
        "sopan, hangat, dan natural. Bisa berbahasa Indonesia, Inggris, Jawa, atau Sunda; ikuti bahasa pengguna. "
        "Jangan menggunakan frasa 'saya asisten AI'. Gunakan data berikut bila relevan:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Status Pendaftaran:\n{reg_status}\n\n"
        f"Riwayat Singkat:\n{json.dumps(short_history, ensure_ascii=False)}"
    )
    user_prompt = (
        f"Tanggal: {TRISAKTI.get('current_context', {}).get('date')} | "
        f"Jam: {TRISAKTI.get('current_context', {}).get('time')}\n"
        f"Pertanyaan: {corrected}\nBahasa: {lang.upper()}\n"
        "Balas singkat, jelas, manusiawi, dan mudah dipahami."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt + "\n\n" + user_prompt
        )
        reply_text = clean_response((response.text or "").strip())
        reply_text = format_links(reply_text)

        # Fallback jika AI tidak tahu jawaban
        if not reply_text or re.search(r"\b(maaf|tidak tahu|belum)\b", reply_text, flags=re.I):
            kontak = TRISAKTI.get("institution", {}).get("contact", {})
            wa = kontak.get("whatsapp")
            ig = kontak.get("instagram")
            wa_link = f"<a href='https://wa.me/{wa.replace('+','')}' target='_blank' rel='noopener'>{wa}</a>" if wa else "Belum tersedia"
            ig_link = f"<a href='https://www.instagram.com/{ig}' target='_blank' rel='noopener'>@{ig}</a>" if ig else "Belum tersedia"
            reply_text = (
                "Maaf, aku belum punya info lengkap buat itu 😅<br>"
                "Hubungi petugas kami ya:<br>"
                f"📱 WhatsApp: {wa_link}<br>"
                f"📸 Instagram: {ig_link}"
            )

        reply_text = sanitize_html(reply_text)
        session["conversation"].append({"role": "bot", "content": reply_text})
        save_chat(corrected, reply_text)
        resp = jsonify({"reply": reply_text})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini API Error: %s", e)
        kontak = TRISAKTI.get("institution", {}).get("contact", {})
        wa = kontak.get("whatsapp", "")
        ig = kontak.get("instagram", "")
        reply_text = (
            "Koneksi AI sedang bermasalah. Coba lagi nanti ya 🙏<br>"
            f"📱 WhatsApp: <a href='https://wa.me/{wa.replace('+','')}' target='_blank' rel='noopener'>{wa}</a><br>"
            f"📸 Instagram: <a href='https://www.instagram.com/{ig}' target='_blank' rel='noopener'>@{ig}</a>"
        )
        reply_text = sanitize_html(reply_text)
        resp = jsonify({"reply": reply_text})
        resp.headers["Cache-Control"] = "no-store"
        return resp, 500
    except Exception as e:
        logger.error("Internal Error: %s", e)
        return jsonify({"error": "Kesalahan sistem internal."}), 500

# -------------------- Security headers --------------------
@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    # Sesuaikan CSP jika perlu load static dari CDN lain
    csp = (
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; form-action 'self'"
    )
    resp.headers.setdefault("Content-Security-Policy", csp)
    return resp

# -------------------- Error handlers --------------------
@app.errorhandler(403)
def forbidden(e):
    return jsonify({"error": "Forbidden"}), 403

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Payload terlalu besar."}), 413

@app.errorhandler(404)
def not_found(e):
    # untuk API berikan JSON, untuk UI pakai 404.html kalau ada
    if request.path.startswith("/api") or request.method == "POST":
        return jsonify({"error": "Endpoint tidak ditemukan."}), 404
    return render_template("404.html"), 404

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Terlalu banyak permintaan. Coba lagi nanti."}), 429

@app.errorhandler(500)
def internal_error(e):
    logger.error("Error 500: %s", e)
    return jsonify({"error": "Terjadi kesalahan di server TIMU."}), 500

# -------------------- Run --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    logger.info("🚀 TIMU berjalan di port %s", port)
    app.run(host="0.0.0.0", port=port)