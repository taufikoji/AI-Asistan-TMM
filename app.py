import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="app.log"
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Flask setup
app = Flask(__name__)
CORS(app)

# Konfigurasi Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gagal konfigurasi Gemini: {e}")

# Load JSON data
try:
    with open("trisakti_info.json", "r", encoding="utf-8") as f:
        TRISAKTI = json.load(f)
except Exception as e:
    logger.critical(f"Gagal memuat data JSON: {e}")
    TRISAKTI = {}

# Simpan riwayat
def save_chat(user, ai):
    try:
        file = "chat_history.json"
        data = []
        if os.path.exists(file):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        data.append({
            "timestamp": datetime.now().isoformat(),
            "user": user,
            "ai": ai
        })
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Gagal simpan riwayat: {e}")

# Deteksi kategori
def get_category(msg):
    msg = msg.lower()
    for kategori, keywords in TRISAKTI.get("faq_keywords", {}).items():
        if any(k in msg for k in keywords):
            return kategori
    return None

# ROUTE INDEX
@app.route("/")
def index():
    return render_template("index.html")

# ROUTE CHAT
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Pesan kosong."}), 400

    kategori = get_category(message)
    system = (
        "Anda adalah asisten AI resmi Trisakti School of Multimedia. "
        "Gunakan bahasa Indonesia formal dan edukatif. Jawaban harus jelas, sopan, dan berdasarkan data kampus berikut:\n\n"
        f"{json.dumps(TRISAKTI, ensure_ascii=False)}\n\n"
    )

    prompt = ""

    if kategori == "kontak":
        kontak = TRISAKTI.get("kontak", {})
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Tuliskan jawaban lengkap dan formal seperti surat informasi resmi institusi. Sertakan:\n"
            f"- Alamat kampus: {TRISAKTI.get('address')}\n"
            f"- Nomor telepon: {', '.join(kontak.get('phone', []))}\n"
            f"- WhatsApp: {kontak.get('whatsapp')}\n"
            f"- Email: {kontak.get('email')}\n"
            f"- Jam operasional: {kontak.get('office_hours')}\n"
            f"- Media sosial: {json.dumps(kontak.get('social_media'), ensure_ascii=False)}"
        )
    elif kategori == "beasiswa":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan semua jenis beasiswa di TSM dengan format formal dan terstruktur, mencakup:\n"
            f"- Nama\n- Deskripsi\n- Syarat\n- Proses\n\n"
            f"{json.dumps(TRISAKTI.get('beasiswa', []), ensure_ascii=False)}"
        )
    elif kategori == "pendaftaran":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan prosedur pendaftaran, jalur masuk, syarat, dan gelombang.\n"
            f"Data pendaftaran: {json.dumps(TRISAKTI.get('registration_details'), ensure_ascii=False)}\n"
            f"Link: {TRISAKTI.get('registration_link')}"
        )
    elif kategori == "prodi":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan semua program studi secara ringkas dan jelas.\n"
            f"{json.dumps(TRISAKTI.get('programs', []), ensure_ascii=False)}"
        )
    elif kategori == "akreditasi":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Tuliskan status akreditasi kampus dan masing-masing program studi.\n"
            f"{json.dumps(TRISAKTI.get('accreditation', {}), ensure_ascii=False)}"
        )
    elif kategori == "fasilitas":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan fasilitas kampus secara rinci dan menarik.\n"
            f"{json.dumps(TRISAKTI.get('facilities', []), ensure_ascii=False)}"
        )
    elif kategori == "jadwal":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan kalender akademik terkini.\n"
            f"{json.dumps(TRISAKTI.get('academic_calendar', {}), ensure_ascii=False)}"
        )
    elif kategori == "sejarah":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan sejarah kampus berdasarkan data berikut:\n"
            f"{TRISAKTI.get('history')}"
        )
    elif kategori == "identitas_kampus":
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jelaskan profil kampus, sejarah, visi, misi, program unggulan, dan nilai-nilai institusi secara ringkas dan formal."
        )
    else:
        prompt = (
            f"Pengguna bertanya: '{message}'\n"
            f"Jawablah secara sopan dan profesional, berdasarkan semua data kampus."
        )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,
                "top_p": 0.9,
                "max_output_tokens": 1024
            }
        )
        result = model.generate_content(system + prompt)
        reply = result.text.strip()
        save_chat(message, reply)
        return jsonify({"reply": reply})
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini API Error: {e}")
        return jsonify({"error": "Koneksi AI gagal"}), 500
    except Exception as e:
        logger.error(f"Error umum: {e}")
        return jsonify({"error": "Kesalahan sistem"}), 500

# Jalankan
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)