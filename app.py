import os
import json
import logging
import re
import time
from datetime import datetime, timedelta
from dateutil.parser import parse as parse_date
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from dotenv import load_dotenv
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
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
BASE_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.join(BASE_DIR, "trisakti_info.json")
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
        "institution": {"contact": {"whatsapp": "+6287742997808", "instagram": "https://www.instagram.com/tmm_trisakti"}},
        "registration": {}
    }

# -------------------- SymSpell (typo correction) --------------------
symspell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
DICT_PATH = os.path.join(BASE_DIR, "indonesia_dictionary_3000.txt")
_symspell_ok = False
try:
    _symspell_ok = symspell.load_dictionary(DICT_PATH, 0, 1)
    if not _symspell_ok:
        logger.warning("⚠️ Kamus SymSpell gagal dimuat. Koreksi typo dinonaktifkan.")
except Exception as e:
    logger.warning("⚠️ Gagal memuat kamus SymSpell: %s", e)
    _symspell_ok = False

def correct_typo(text):
    if not _symspell_ok or not text:
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

    def repl(match):
        url = match.group(0)
        if re.search(r"<a\s+href=", url, flags=re.I):
            return url
        normalized = url.strip().rstrip("/").lower()
        if normalized in seen:
            return ""
        seen.add(normalized)
        return f"<a href='{url}' target='_blank' rel='noopener noreferrer'>🔗 {url}</a>"

    pattern = r"(?<!href=['\"])(https?://[^\s<>'\"()]+)"
    formatted = re.sub(pattern, repl, text)
    formatted = re.sub(r"\s{2,}", " ", formatted).strip()
    return formatted

def save_chat(user_msg, ai_msg):
    try:
        fname = os.path.join(BASE_DIR, "chat_history.json")
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
    # simple fallback checks
    if any(k in msg for k in ["brosur", "brosur tmm", "brosur resmi"]):
        return "brosur"
    if any(k in msg for k in ["pendaftaran", "daftar", "tanggal pendaftaran", "gelombang"]):
        return "pendaftaran"
    return "general"

# -------------------- Admission scraping & caching --------------------
EADMISI_URL = TRISAKTI.get("registration", {}).get("source", "https://trisaktimultimedia.ecampuz.com/eadmisi/")
CACHE_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "admission_cache.json")
CACHE_TTL_SECONDS = int(os.getenv("ADMISSION_CACHE_TTL_SECONDS", 6 * 3600))  # default 6 hours

def _write_cache(data):
    try:
        payload = {"fetched_at": time.time(), "data": data}
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("✅ Admission cache disimpan.")
    except Exception as e:
        logger.warning("Gagal menyimpan admission cache: %s", e)

def _read_cache():
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        payload = json.load(open(CACHE_FILE, encoding="utf-8"))
        return payload
    except Exception as e:
        logger.warning("Gagal membaca admission cache: %s", e)
        return None

def fetch_admission_from_eadmisi(url=EADMISI_URL):
    """
    Coba ambil informasi pendaftaran dari halaman eAdmisi.
    Hasil dikembalikan dalam struktur sederhana:
    {
      "source": url,
      "paths": [
        {"name": "EB - Early Bird", "link": "...", "waves": [{"wave":"Gelombang 1","period":"01 Oct 2025 - 31 Dec 2025", "notes": "..."}], "raw_text": "..."}
      ],
      "raw_html": "..."
    }
    Fungsi ini dibuat toleran karena struktur HTML ecampuz bisa berbeda.
    """
    logger.info("Mencoba fetch eAdmisi dari: %s", url)
    try:
        resp = requests.get(url, timeout=12)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {"source": url, "paths": [], "raw_html": ""}
        result["raw_html"] = resp.text[:40000]  # simpan sebagian untuk debugging

        # Cari blok yang berhubungan dengan pendaftaran: headings yang mengandung kata kunci
        candidates = []
        for tag in soup.find_all(["section", "div", "article", "main"]):
            text = tag.get_text(separator=" ", strip=True).lower()
            if any(k in text for k in ["pendaftaran", "gelombang", "daftar", "tanggal pendaftaran", "early bird", "jadwal pendaftaran"]):
                candidates.append(tag)

        # Jika tidak ada candidate, fallback ke seluruh body
        if not candidates:
            body = soup.body
            if body:
                candidates = [body]

        # Dari candidate, cari link pendaftaran dan periode tanggal
        paths = []
        for c in candidates:
            raw = c.get_text(separator="\n", strip=True)
            links = []
            for a in c.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(strip=True)
                if href and href.startswith("http"):
                    links.append({"href": href, "text": text})
            # mencari pola tanggal dalam teks candidate
            waves = []
            # cari semua kemungkinan teks yang mengandung kata 'gelombang' atau rentang tanggal
            lines = raw.splitlines()
            for line in lines:
                low = line.lower()
                if "gelombang" in low or "early" in low or re.search(r"\d{1,2}\s+\w+\s+\d{4}", line):
                    # coba ekstrak periode rentang tanggal
                    # pola umum: "01 Oktober 2025 - 31 Desember 2025" atau "01 Oct 2025 - 31 Dec 2025"
                    matches = re.findall(r"(\d{1,2}\s+[A-Za-zāéíóúâäàèêôû]+\s+\d{4}\s*[-–]\s*\d{1,2}\s+[A-Za-zāéíóúâäàèêôû]+\s+\d{4})", line)
                    if not matches:
                        # alternatif: 01/10/2025 - 31/12/2025
                        matches = re.findall(r"(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}\s*[-–]\s*\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})", line)
                    if matches:
                        for m in matches:
                            waves.append({"wave": line.strip(), "period": m.strip(), "notes": ""})
                    else:
                        # tambahkan sebagai keterangan tanpa period yang jelas
                        waves.append({"wave": line.strip(), "period": "", "notes": ""})

            path_name = None
            if links:
                path_name = links[0].get("text") or links[0].get("href")
            else:
                # coba ambil heading paling dekat
                heading = c.find(["h1","h2","h3","h4","strong","b"])
                if heading:
                    path_name = heading.get_text(strip=True)

            if waves or links or path_name:
                paths.append({
                    "name": path_name or "Pendaftaran",
                    "link": links[0]["href"] if links else url,
                    "waves": waves if waves else [{"wave": "Info", "period": "", "notes": raw[:300]}],
                    "raw_text": raw[:2000]
                })

        # dedup paths by link
        unique = []
        seen_links = set()
        for p in paths:
            link = p.get("link","").strip()
            if link in seen_links:
                continue
            seen_links.add(link)
            unique.append(p)

        result["paths"] = unique if unique else [{"name": "Pendaftaran", "link": url, "waves": [], "raw_text": ""}]
        _write_cache(result)
        logger.info("✅ Berhasil fetch eAdmisi, ditemukan %d path(s)", len(result["paths"]))
        return result
    except Exception as e:
        logger.warning("Gagal fetch eAdmisi: %s", e)
        return None

def get_admission_data(force_refresh=False):
    """
    Kembalikan data admission yang tersedia, prioritas:
    1) Jika force_refresh=True => coba fetch langsung, jika sukses gunakan itu.
    2) Jika cache ada dan masih TTL => gunakan cache.
    3) Coba fetch sekali.
    4) Fallback ke TRISAKTI['registration'] (static JSON).
    """
    try:
        if force_refresh:
            live = fetch_admission_from_eadmisi()
            if live:
                return live

        cache = _read_cache()
        if cache:
            age = time.time() - cache.get("fetched_at", 0)
            if age <= CACHE_TTL_SECONDS:
                logger.info("Menggunakan admission cache (age=%ds)", int(age))
                return cache.get("data")
            else:
                # cache kadaluwarsa, coba fetch
                live = fetch_admission_from_eadmisi()
                if live:
                    return live
                # gunakan cache yang kadaluwarsa sebagai fallback
                logger.info("Menggunakan admission cache yang kadaluwarsa sebagai fallback.")
                return cache.get("data")

        # tidak ada cache, coba fetch
        live = fetch_admission_from_eadmisi()
        if live:
            return live

        # fallback ke TRISAKTI static
        reg_static = TRISAKTI.get("registration", {})
        logger.info("Menggunakan data pendaftaran statis dari trisakti_info.json")
        return {"source": "static", "paths": reg_static.get("paths", []), "link": reg_static.get("link", "")}
    except Exception as e:
        logger.warning("Error get_admission_data: %s", e)
        return {"source": "error", "paths": []}

def parse_period_to_dates(period_str):
    """
    Coba konversi teks period menjadi (start_date, end_date) sebagai date object.
    Jika gagal, return (None, None).
    """
    if not period_str:
        return (None, None)
    try:
        # replace beberapa pemisah umum
        period_str = period_str.replace("–", "-").replace("—", "-")
        # split on dash
        if "-" in period_str:
            start_s, end_s = [s.strip() for s in period_str.split("-", 1)]
            start = parse_date(start_s, dayfirst=True, fuzzy=True).date()
            end = parse_date(end_s, dayfirst=True, fuzzy=True).date()
            return (start, end)
        # jika hanya satu tanggal
        d = parse_date(period_str, dayfirst=True, fuzzy=True).date()
        return (d, d)
    except Exception:
        return (None, None)

def get_current_registration_status():
    """
    Menghasilkan teks status pendaftaran berdasarkan data admission (live/cache/static).
    """
    try:
        today = datetime.now().date()
        ad = get_admission_data()
        out = []
        for p in ad.get("paths", []):
            name = p.get("name") or p.get("link") or "Pendaftaran"
            waves = p.get("waves", []) or []
            if not waves:
                out.append(f"{name}: Info pendaftaran tersedia di <a href='{p.get('link')}' target='_blank'>{p.get('link')}</a>")
                continue
            for w in waves:
                period = w.get("period", "") or ""
                wave_name = w.get("wave", "Gelombang")
                start, end = parse_period_to_dates(period)
                if start and end:
                    if today < start:
                        out.append(f"{wave_name} ({name}) akan dibuka {start.strftime('%d %B %Y')} hingga {end.strftime('%d %B %Y')}.")
                    elif start <= today <= end:
                        out.append(f"{wave_name} ({name}) sedang berlangsung hingga {end.strftime('%d %B %Y')}.")
                    else:
                        out.append(f"{wave_name} ({name}) sudah ditutup {end.strftime('%d %B %Y')}.")
                else:
                    # tidak ada periode terstruktur, tampilkan snippet teks / link
                    snippet = (w.get("notes") or p.get("raw_text") or "")[:180]
                    if snippet:
                        out.append(f"{wave_name} ({name}): {snippet} <br>Selengkapnya: <a href='{p.get('link')}' target='_blank'>{p.get('link')}</a>")
                    else:
                        out.append(f"{wave_name} ({name}): Info pendaftaran di <a href='{p.get('link')}' target='_blank'>{p.get('link')}</a>")
        return "\n".join(out) if out else "Belum ada informasi pendaftaran."
    except Exception as e:
        logger.warning("Gagal menentukan status pendaftaran: %s", e)
        return "Status pendaftaran tidak tersedia."

# -------------------- Program alias lookup --------------------
def find_program_by_alias(query):
    q = query.lower()
    for prog in TRISAKTI.get("academic_programs", []):
        for a in prog.get("aliases", []):
            if a and a.lower() in q:
                return prog
            if q in (a or "").lower():
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
        with open(os.path.join(BASE_DIR, "chat_history.json"), "r", encoding="utf-8") as f:
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

@app.route("/api/refresh-admission-cache", methods=["POST"])
def api_refresh_admission_cache():
    """
    Endpoint admin untuk memaksa refresh data admission (mis. dipanggil dari admin panel).
    """
    if not session.get("admin_logged_in"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        live = fetch_admission_from_eadmisi()
        if live:
            return jsonify({"ok": True, "source": "live", "paths": live.get("paths", [])})
        else:
            return jsonify({"ok": False, "error": "Gagal fetch live data"}), 500
    except Exception as e:
        logger.error("Error refresh admission cache: %s", e)
        return jsonify({"error": str(e)}), 500

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
        ad = get_admission_data()
        links = []
        for p in ad.get("paths", []):
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

    # Build prompts for Gemini
    short_history = session.get("conversation", [])[-6:]
    system_prompt = (
        "Kamu adalah TIMU, asisten AI Trisakti School of Multimedia (TMM). "
        "kamu harus ramah dan dapat berinteraksi dengan baik. "
        "kamu harus ekspresif dan dapat diajak bercanda ringan. "
        "kamu ahli dalam berbagai bahasa apapun namun bahasa utama kamu mengikuti bahasa pengguna. "
        "Jawablah dengan sopan dan ringkas dalam bahasa pengguna. Gunakan data institusi berikut jika relevan:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\nStatus Pendaftaran:\n{reg_status}\n\n"
        f"Riwayat Singkat:\n{json.dumps(short_history, ensure_ascii=False)}"
    )
    user_prompt = (
        f"Tanggal: {TRISAKTI.get('current_context', {}).get('date')} | Jam: {TRISAKTI.get('current_context', {}).get('time')}\n"
        f"Pertanyaan: {corrected}\nBahasa: {lang.upper()}\nJawablah singkat, informatif, dan mudah dipahami."
    )

    try:
        # Memanggil Gemini (model yang Anda gunakan sebelumnya)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt + "\n\n" + user_prompt
        )
        reply_text = clean_response(response.text.strip())
        reply_text = format_links(reply_text)

        # Jika jawaban tidak memadai, fallback kepada kontak institusi
        if not reply_text or re.search(r"\b(maaf|tidak tahu|belum)\b", reply_text, flags=re.I):
            kontak = TRISAKTI.get("institution", {}).get("contact", {})
            wa = kontak.get("whatsapp", "")
            ig = kontak.get("instagram", "")
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
        wa = kontak.get("whatsapp", "")
        ig = kontak.get("instagram", "")
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