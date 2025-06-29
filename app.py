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

# Konfigurasi Gemini
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# Logging
logging.basicConfig(level=logging.INFO)
log_file = "chat_history.json"
data_file = "trisakti_info.json"

# Flask app
app = Flask(__name__)
CORS(app)

# Load data JSON
with open(data_file, "r", encoding="utf-8") as f:
    kampus_data = json.load(f)

# Fungsi pencocokan kategori
def temukan_kategori(pertanyaan):
    for kategori, keywords in kampus_data.get("faq_keywords", {}).items():
        if any(k.lower() in pertanyaan.lower() for k in keywords):
            return kategori
    return None

# Fungsi jawaban dari data lokal
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

# Fallback dengan Gemini
def jawab_dengan_gemini(prompt):
    try:
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except google_exceptions.GoogleAPIError as e:
        logging.error(f"[Gemini Error] {e}")
        return None
    except Exception as e:
        logging.error(f"[Unhandled Gemini Error] {e}")
        return None

# Endpoint utama
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_input = data.get("message", "")
    waktu = datetime.now().isoformat()

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

    # Logging chat
    log = {
        "waktu": waktu,
        "pertanyaan": user_input,
        "jawaban": jawaban,
        "sumber": sumber
    }
    try:
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                riwayat = json.load(f)
        else:
            riwayat = []
        riwayat.append(log)
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(riwayat, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"[Log Error] {e}")

    return jsonify({"response": jawaban, "source": sumber})

# Halaman utama
@app.route("/")
def index():
    return render_template("index.html")

# Jalankan app
if __name__ == "__main__":
    app.run(debug=True, port=5000)