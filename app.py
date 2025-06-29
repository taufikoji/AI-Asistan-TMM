import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from flask_cors import CORS
from datetime import datetime
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "trisakti_info.json")
LOG_FILE = os.path.join(BASE_DIR, "chat_history.json")

# Load data JSON
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        kampus_data = json.load(f)
except FileNotFoundError:
    logger.error(f"Data file {DATA_FILE} not found")
    raise
except json.JSONDecodeError:
    logger.error(f"Invalid JSON in {DATA_FILE}")
    raise

# Function to match category
def temukan_kategori(pertanyaan):
    if not pertanyaan or not isinstance(pertanyaan, str):
        return None
    for kategori, keywords in kampus_data.get("faq_keywords", {}).items():
        if any(k.lower() in pertanyaan.lower() for k in keywords):
            return kategori
    return None

# Function to generate answer from local data
def jawab_dari_data(kategori):
    if kategori == "kontak":
        kontak = kampus_data["kontak"]
        return f"""
Selamat datang di Trisakti School of Multimedia (TMM).

Untuk informasi dan komunikasi resmi, berikut data kontak kami:
- 📍 **Alamat:** {kampus_data['address']}
- ☎️ **Telepon:** {', '.join(kontak['phone'])}
- 📧 **Email:** {kontak['email']}
- 📱 **WhatsApp:** {kontak['whatsapp']}
- 🕗 **Jam Operasional:** {kontak['office_hours']}
- 📲 **Instagram:** {kontak['social_media']['instagram']}
- 📘 **Facebook:** {kontak['social_media']['facebook']}

Kami siap melayani Anda pada hari kerja. Jangan ragu untuk menghubungi kami!
"""
    elif kategori == "alamat":
        return f"Alamat kampus Trisakti School of Multimedia (TMM):\n{kampus_data['address']}"
    elif kategori == "sejarah":
        return kampus_data["history"]
    elif kategori == "visimisi":
        return f"Visi:\n{kampus_data['vision']}\n\nMisi:\n- " + "\n- ".join(kampus_data["mission"])
    elif kategori == "keunggulan":
        return kampus_data["why_trisakti"]
    elif kategori == "fasilitas":
        return "Fasilitas kampus:\n- " + "\n- ".join(kampus_data["facilities"])
    elif kategori == "akreditasi":
        ak = kampus_data["accreditation"]
        teks = f"Akreditasi institusi: {ak['overall']}\n\nAkreditasi program studi:"
        for prodi, nilai in ak["programs"].items():
            teks += f"\n- {prodi}: {nilai}"
        return teks
    elif kategori == "prodi":
        hasil = []
        for p in kampus_data["programs"]:
            hasil.append(f"- **{p['name']}**\n  Akreditasi: {p['accreditation']}\n  Deskripsi: {p['description']}")
        return "\n\n".join(hasil)
    elif kategori == "pendaftaran":
        link = kampus_data["registration_link"]
        detail = kampus_data["registration_details"]
        persyaratan = "\n- ".join(detail["requirements"])
        jalur = ""
        for path in detail["paths"]:
            jalur += f"\n• {path['name']}:\n"
            for gel in path["waves"]:
                jalur += f"  - {gel['wave']}: {gel['period']}\n"
        return f"Pendaftaran dilakukan secara online melalui:\n{link}\n\n**Syarat Umum:**\n- {persyaratan}\n\n**Jalur Pendaftaran:**{jalur}"
    elif kategori == "beasiswa":
        b = kampus_data["beasiswa"]
        teks = []
        for bea in b:
            teks.append(f"🎓 {bea['name']}\nDeskripsi: {bea['description']}\nSyarat:\n- " + "\n- ".join(bea['requirements']) + f"\nProses: {bea['process']}")
        return "\n\n".join(teks)
    elif kategori == "berita":
        hasil = [f"📰 {n['title']} ({n['date']}): {n['description']}" for n in kampus_data["news"]]
        return "\n\n".join(hasil)
    elif kategori == "jadwal":
        sem1 = kampus_data["academic_calendar"]["semester_1_2025"]
        sem2 = kampus_data["academic_calendar"]["semester_2_2025"]
        return f"📅 Semester 1:\n- Mulai: {sem1['start']}\n- Selesai: {sem1['end']}\n- Libur: {', '.join(sem1['holidays'])}\n\n📅 Semester 2:\n- Mulai: {sem2['start']}\n- Selesai: {sem2['end']}\n- Libur: {', '.join(sem2['holidays'])}"
    elif kategori == "testimoni":
        alumni = kampus_data["alumni_testimonials"]
        return "\n\n".join([f"👨‍🎓 {a['name']} ({a['program']}, {a['year']}):\n\"{a['testimonial']}\"" for a in alumni])
    elif kategori == "identitas_kampus":
        return f"Trisakti School of Multimedia (TMM), sebelumnya dikenal sebagai STMK Trisakti, adalah perguruan tinggi di bidang media komunikasi dan industri kreatif, berdiri sejak tahun {kampus_data['foundation_year']}."
    return None

# Fallback with Gemini
def jawab_dengan_gemini(prompt):
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Gemini API error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Gemini error: {e}")
        return None

# Chat endpoint
@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "No message provided"}), 400
        
        user_input = data["message"].strip()
        if not user_input:
            return jsonify({"error": "Empty message"}), 400
        if len(user_input) > 500:
            return jsonify({"error": "Message too long (max 500 characters)"}), 400

        waktu = datetime.utcnow().isoformat()
        kategori = temukan_kategori(user_input)
        jawaban = None
        sumber = None

        if kategori:
            jawaban = jawab_dari_data(kategori)
            sumber = "data lokal"

        if not jawaban:
            jawaban = jawab_dengan_gemini(user_input)
            sumber = "AI Gemini" if jawaban else "error"

        if not jawaban:
            jawaban = "Maaf, saat ini saya belum dapat menjawab pertanyaan Anda."
            sumber = "error"

        # Log chat
        log = {
            "waktu": waktu,
            "pertanyaan": user_input,
            "jawaban": jawaban,
            "sumber": sumber
        }
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    riwayat = json.load(f)
            else:
                riwayat = []
            riwayat.append(log)
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(riwayat, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to log chat: {e}")

        return jsonify({"response": jawaban, "source": sumber})
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Main page
@app.route("/")
def index():
    return render_template("index.html")

# Run app
if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)