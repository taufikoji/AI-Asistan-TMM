import os
import json
import logging
import re
import sqlite3
from datetime import datetime, timedelta, date
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
from flask_session import Session
import bleach
from difflib import SequenceMatcher

# ==================== Logging ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# ==================== ENV ====================
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("❌ GEMINI_API_KEY tidak ditemukan!")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FLASK_SECRET = os.getenv("FLASK_SECRET_KEY", "timu-secret-key")

# Whitelist origin (WordPress + Render)
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://ai-asistan-tmm.onrender.com,https://trisaktimultimedia.ac.id,https://www.trisaktimultimedia.ac.id"
    ).split(",") if o.strip()
]
# Auto-allow domain Render aktif
_render_url = os.getenv("RENDER_EXTERNAL_URL")
if _render_url and _render_url not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(_render_url)

# Storage paths (Render-safe). Gunakan DB_PATH jika ada volume persisten.
TMP_DIR = "/tmp"
SESSION_DIR = os.path.join(TMP_DIR, "flask_session")
DEFAULT_DB_PATH = os.path.join(TMP_DIR, "timu.db")
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)
CHAT_JSON_BACKUP = os.path.join(TMP_DIR, "chat_history_backup.json")
BACKUP_JSON = os.getenv("BACKUP_JSON", "0") == "1"

os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ==================== Flask init ====================
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = FLASK_SECRET

# Trust proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Session & security
app.config.update(
    SESSION_TYPE="filesystem",
    SESSION_FILE_DIR=SESSION_DIR,
    SESSION_PERMANENT=False,
    SESSION_USE_SIGNER=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=16 * 1024,  # 16KB
    PERMANENT_SESSION_LIFETIME=timedelta(hours=6),
    PREFERRED_URL_SCHEME="https",
)
Session(app)

# CORS & Rate limit
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})
limiter = Limiter(get_remote_address, app=app,
                  default_limits=["600 per hour", "60 per minute"])

# ==================== Gemini client ====================
client = genai.Client(api_key=GEMINI_API_KEY)

# ==================== Load JSON data ====================
JSON_PATH = os.path.join(os.path.dirname(__file__), "trisakti_info.json")
try:
    with open(JSON_PATH, "r", encoding="utf-8") as jf:
        TRISAKTI = json.load(jf)
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

# ==================== SymSpell ====================
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

# ==================== Utils ====================
def detect_language(text: str) -> str:
    try:
        if len(text.strip().split()) < 3:
            return "id"
        return detect(text) or "id"
    except Exception:
        return "id"

def clean_response(text):
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

# XSS guard
BLEACH_TAGS = ["a", "b", "strong", "em", "br"]
BLEACH_ATTRS = {"a": ["href", "target", "rel"]}
BLEACH_PROTOCOLS = ["http", "https"]
def sanitize_html(html_text: str) -> str:
    return bleach.clean(html_text or "", tags=BLEACH_TAGS, attributes=BLEACH_ATTRS,
                        protocols=BLEACH_PROTOCOLS, strip=True)

# ==================== SQLite Layer ====================
def db_conn():
    return sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)

def init_db():
    with db_conn() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            user_msg TEXT NOT NULL,
            ai_msg TEXT NOT NULL,
            source TEXT NOT NULL
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS ai_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_norm TEXT NOT NULL,
            answer TEXT NOT NULL,
            ts TEXT NOT NULL,
            hits INTEGER NOT NULL DEFAULT 0
        )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cache_q ON ai_cache(question_norm)")
        conn.commit()

def save_chat_db(user_msg: str, ai_msg: str, source: str = "ai"):
    try:
        with db_conn() as conn:
            conn.execute(
                "INSERT INTO chat_history (ts, user_msg, ai_msg, source) VALUES (?, ?, ?, ?)",
                (datetime.now().isoformat(), user_msg, ai_msg, source)
            )
            conn.commit()
    except Exception as e:
        logger.warning("Gagal insert chat_history: %s", e)

def read_latest_chats(limit=5):
    try:
        with db_conn() as conn:
            cur = conn.execute(
                "SELECT ts, user_msg, ai_msg, source FROM chat_history ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cur.fetchall()
            return [{"timestamp": r[0], "user": r[1], "ai": r[2], "source": r[3]} for r in rows][::-1]
    except Exception as e:
        logger.warning("Gagal read_latest_chats: %s", e)
        return []

def stats_overview():
    try:
        with db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
            today = conn.execute(
                "SELECT COUNT(*) FROM chat_history WHERE date(ts)=date('now','localtime')"
            ).fetchone()[0]
            cache_hits = conn.execute(
                "SELECT COALESCE(SUM(hits),0) FROM ai_cache"
            ).fetchone()[0]
            top = conn.execute("""
                SELECT question_norm, COUNT(*) as cnt
                FROM (
                    SELECT LOWER(TRIM(user_msg)) as question_norm FROM chat_history
                )
                GROUP BY question_norm
                ORDER BY cnt DESC
                LIMIT 5
            """).fetchall()
            top_list = [{"question": r[0], "count": r[1]} for r in top]
            return {"total": total, "today": today, "cache_hits": cache_hits, "top": top_list}
    except Exception as e:
        logger.warning("Gagal stats_overview: %s", e)
        return {"total": 0, "today": 0, "cache_hits": 0, "top": []}

# ====== Cache helpers (SQLite) ======
CACHE_MAX_ENTRIES = 2000
SIM_THRESHOLD_HIT = 0.82
SIM_THRESHOLD_DEDUP = 0.95

def _norm_q(q: str) -> str:
    q = (q or "").lower().strip()
    q = re.sub(r"[^\w\s]", " ", q)
    q = re.sub(r"\s+", " ", q)
    return q

def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm_q(a), _norm_q(b)).ratio()

def cache_get_answer(user_msg: str):
    try:
        qn = _norm_q(user_msg)
        with db_conn() as conn:
            # ambil kandidat kecil (LIKE) untuk efisiensi
            token = qn.split(" ")[0] if qn else ""
            if token:
                cur = conn.execute(
                    "SELECT id, question_norm, answer, hits FROM ai_cache WHERE question_norm LIKE ?",
                    (f"%{token}%",)
                )
                candidates = cur.fetchall()
            else:
                candidates = conn.execute("SELECT id, question_norm, answer, hits FROM ai_cache").fetchall()

            best_id, best_ans, best_score = None, None, 0.0
            for cid, cq, ca, hits in candidates:
                sc = _similar(cq, user_msg)
                if sc > best_score:
                    best_id, best_ans, best_score = cid, ca, sc

            if best_id and best_score >= SIM_THRESHOLD_HIT:
                conn.execute("UPDATE ai_cache SET hits = hits + 1 WHERE id = ?", (best_id,))
                conn.commit()
                logger.info("💾 Cache HIT (%.2f): %s", best_score, user_msg[:80])
                return best_ans
    except Exception as e:
        logger.warning("cache_get_answer error: %s", e)
    return None

def cache_put_answer(user_msg: str, answer: str):
    if not user_msg or not answer:
        return
    try:
        qn = _norm_q(user_msg)
        with db_conn() as conn:
            # dedup by similarity
            cur = conn.execute("SELECT id, question_norm FROM ai_cache")
            for cid, cq in cur.fetchall():
                if _similar(cq, user_msg) >= SIM_THRESHOLD_DEDUP:
                    conn.execute(
                        "UPDATE ai_cache SET answer=?, ts=?, hits=0 WHERE id=?",
                        (answer, datetime.now().isoformat(), cid)
                    )
                    conn.commit()
                    return
            # trim jika melebihi kapasitas
            count = conn.execute("SELECT COUNT(*) FROM ai_cache").fetchone()[0]
            if count >= CACHE_MAX_ENTRIES:
                conn.execute("DELETE FROM ai_cache WHERE id IN (SELECT id FROM ai_cache ORDER BY ts ASC LIMIT 100)")
            conn.execute(
                "INSERT INTO ai_cache (question_norm, answer, ts, hits) VALUES (?, ?, ?, 0)",
                (qn, answer, datetime.now().isoformat())
            )
            conn.commit()
    except Exception as e:
        logger.warning("cache_put_answer error: %s", e)

# ==================== Kategori & Pendaftaran ====================
def get_category(msg):
    msg = msg.lower()
    for cat, keys in (TRISAKTI.get("keywords") or {}).items():
        for k in keys:
            if k in msg:
                return cat
    return "general"

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
        name = (prog.get("name") or "").lower()
        if name and (name in q or q in name):
            return prog
        for a in (prog.get("aliases") or []):
            if a and (a.lower() in q or q in a.lower()):
                return prog
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

# ==================== Origin/Size Guard ====================
def _is_allowed_origin(req) -> bool:
    origin = req.headers.get("Origin") or ""
    referer = req.headers.get("Referer") or ""
    if origin and any(origin.startswith(o) for o in ALLOWED_ORIGINS):
        return True
    if referer and any(referer.startswith(o) for o in ALLOWED_ORIGINS):
        return True
    return os.getenv("ALLOW_TESTING", "0") == "1"

def _precheck_request():
    if not _is_allowed_origin(request):
        abort(403)
    if request.content_length and request.content_length > 4 * 1024:
        abort(413)

# ==================== Routes (UI) ====================
@app.route("/")
@limiter.limit("30/minute")
def landing():
    session.clear()
    return render_template("landing.html")

@app.route("/chat")
@limiter.limit("30/minute")
def chatroom():
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
    ov = stats_overview()
    latest = read_latest_chats(limit=5)
    return render_template("stats.html", stats={
        "total_chats": ov["total"],
        "today": ov["today"],
        "cache_hits": ov["cache_hits"],
        "top_questions": ov["top"],
        "latest": latest
    })

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

# ==================== API ====================
# GET init untuk load history sesi (untuk front-end)
@app.route("/api/chat", methods=["GET", "POST"])
@limiter.limit("60/minute")
def api_chat():
    if request.method == "GET":
        if not _is_allowed_origin(request):
            abort(403)
        return jsonify({"conversation": session.get("conversation", [])})
    _precheck_request()
    return _chat_handler()

# Endpoint kompatibel widget yang POST ke /chat
@app.route("/chat", methods=["POST"])
@limiter.limit("60/minute")
def chat_from_widget():
    _precheck_request()
    return _chat_handler()

@app.route("/api/clear-session", methods=["POST"])
@limiter.limit("15/minute")
def clear_session():
    _precheck_request()
    session.pop("conversation", None)
    return jsonify({"ok": True})

# ==================== Core chat handler ====================
def _daily_backup_json(history_row):
    if not BACKUP_JSON:
        return
    try:
        # backup sekali per hari (append)
        today_str = date.today().isoformat()
        data = []
        if os.path.exists(CHAT_JSON_BACKUP):
            with open(CHAT_JSON_BACKUP, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f) or []
                except Exception:
                    data = []
        data.append(history_row)
        with open(CHAT_JSON_BACKUP, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Backup JSON gagal: %s", e)

def _append_session(role, content):
    session.setdefault("conversation", [])
    session["conversation"].append({"role": role, "content": content})
    session["conversation"] = session["conversation"][-50:]

def _chat_handler():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Pesan kosong."}), 400
    if len(message) > 1000:
        return jsonify({"error": "Pesan terlalu panjang (max 1000 karakter)."}), 413

    lang = detect_language(message)
    corrected = correct_typo(message)
    _append_session("user", corrected)

    category = get_category(corrected)
    reg_status = get_current_registration_status()

    # Quick replies
    quick_replies = {
        "ga": "Oke 😊",
        "nggak": "Siap, nggak masalah kok 😄",
        "enggak": "Baiklah 😌",
        "iya": "Iya, siap! 🙌",
        "ok": "Oke 👍",
        "oke": "Siap~ 🚀",
        "wkwk": "Hehe 😆",
        "hmm": "Hmm, bisa dijelasin sedikit lagi?"
    }
    msg_lower = corrected.lower().strip()
    if msg_lower in quick_replies:
        reply = sanitize_html(quick_replies[msg_lower])
        _append_session("bot", reply)
        save_chat_db(corrected, reply, source="quick")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "quick"})
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Kategori data lokal
    if category == "brosur":
        brosur_url = url_for("download_brosur", _external=True)
        reply = f"📄 Brosur resmi TMM siap diunduh:<br><a href='{brosur_url}' target='_blank' rel='noopener'>⬇️ Unduh Brosur</a>"
        reply = sanitize_html(reply)
        _append_session("bot", reply)
        save_chat_db(corrected, reply, source="local")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "local"})
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
        _append_session("bot", reply)
        save_chat_db(corrected, reply, source="local")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "local"})
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Prodi
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
        _append_session("bot", reply)
        save_chat_db(corrected, reply, source="local-prodi")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "local-prodi"})
        resp = jsonify({"reply": reply})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # Cache sebelum AI
    cached = cache_get_answer(corrected)
    if cached:
        reply = sanitize_html(cached)
        _append_session("bot", reply)
        save_chat_db(corrected, reply, source="cache")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "cache"})
        resp = jsonify({"reply": reply, "source": "cache"})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # AI
    short_history = session.get("conversation", [])[-6:]
    system_prompt = (
        "Kamu adalah TIMU, asisten dari Trisakti School of Multimedia (TMM). "
        "Gaya bicara: manusiawi, hangat, ringkas, tidak kaku. "
        "Gunakan BAHASA INDONESIA sebagai default. "
        "Gunakan bahasa lain (Inggris/Jawa/Sunda) HANYA jika pengguna menulis dalam bahasa tersebut. "
        "Jangan menyebut 'saya asisten AI'. Gunakan data berikut bila relevan:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
        f"Status Pendaftaran:\n{reg_status}\n\n"
        f"Riwayat Singkat:\n{json.dumps(short_history, ensure_ascii=False)}"
    )
    user_prompt = (
        f"Tanggal: {TRISAKTI.get('current_context', {}).get('date')} | "
        f"Jam: {TRISAKTI.get('current_context', {}).get('time')}\n"
        f"Pertanyaan: {corrected}\nBahasa terdeteksi: {lang.upper()}\n"
        "Balas singkat, jelas, dan natural."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt + "\n\n" + user_prompt
        )
        reply_text = clean_response((response.text or "").strip())
        if not reply_text:
            cached2 = cache_get_answer(corrected)
            if cached2:
                reply = sanitize_html(format_links(cached2))
                _append_session("bot", reply)
                save_chat_db(corrected, reply, source="cache")
                _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "cache"})
                resp = jsonify({"reply": reply, "source": "cache"})
                resp.headers["Cache-Control"] = "no-store"
                return resp
            kontak = TRISAKTI.get("institution", {}).get("contact", {})
            wa = kontak.get("whatsapp")
            ig = kontak.get("instagram")
            wa_link = f"<a href='https://wa.me/{wa.replace('+','')}' target='_blank' rel='noopener'>{wa}</a>" if wa else "Belum tersedia"
            ig_link = f"<a href='https://www.instagram.com/{ig}' target='_blank' rel='noopener'>@{ig}</a>" if ig else "Belum tersedia"
            reply_text = (
                "Aku belum punya info lengkap untuk itu 😅<br>"
                "Hubungi petugas kami ya:<br>"
                f"📱 WhatsApp: {wa_link}<br>"
                f"📸 Instagram: {ig_link}"
            )

        reply_text = format_links(reply_text)
        reply_text = sanitize_html(reply_text)
        try:
            cache_put_answer(corrected, reply_text)
        except Exception as e:
            logger.warning("Cache put error: %s", e)

        _append_session("bot", reply_text)
        save_chat_db(corrected, reply_text, source="ai")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply_text, "source": "ai"})
        resp = jsonify({"reply": reply_text, "source": "ai"})
        resp.headers["Cache-Control"] = "no-store"
        return resp

    except google_exceptions.GoogleAPIError as e:
        logger.error("Gemini API Error: %s", e)
        cached3 = cache_get_answer(corrected)
        if cached3:
            reply = sanitize_html(format_links(cached3))
            _append_session("bot", reply)
            save_chat_db(corrected, reply, source="cache")
            _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply, "source": "cache"})
            resp = jsonify({"reply": reply, "source": "cache"})
            resp.headers["Cache-Control"] = "no-store"
            return resp
        kontak = TRISAKTI.get("institution", {}).get("contact", {})
        wa = kontak.get("whatsapp", "")
        ig = kontak.get("instagram", "")
        reply_text = (
            "Koneksi AI sedang bermasalah. Coba lagi nanti ya 🙏<br>"
            f"📱 WhatsApp: <a href='https://wa.me/{wa.replace('+','')}' target='_blank' rel='noopener'>{wa}</a><br>"
            f"📸 Instagram: <a href='https://www.instagram.com/{ig}' target='_blank' rel='noopener'>@{ig}</a>"
        )
        reply_text = sanitize_html(reply_text)
        _append_session("bot", reply_text)
        save_chat_db(corrected, reply_text, source="fallback")
        _daily_backup_json({"timestamp": datetime.now().isoformat(), "user": corrected, "ai": reply_text, "source": "fallback"})
        resp = jsonify({"reply": reply_text, "source": "fallback"})
        resp.headers["Cache-Control"] = "no-store"
        return resp, 500
    except Exception as e:
        logger.error("Internal Error: %s", e)
        return jsonify({"error": "Kesalahan sistem internal."}), 500

# ==================== Security headers ====================
@app.after_request
def add_security_headers(resp):
    resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
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

# ==================== Errors ====================
@app.errorhandler(403)
def forbidden(e):
    return jsonify({"error": "Forbidden"}), 403

@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "Payload terlalu besar."}), 413

@app.errorhandler(404)
def not_found(e):
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

# ==================== Main ====================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    logger.info("TIMU berjalan di port %s, DB=%s", port, DB_PATH)
    app.run(host="0.0.0.0", port=port)