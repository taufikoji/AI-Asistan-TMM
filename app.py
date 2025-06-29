import os
import json
import logging
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core import exceptions as google_ex
import requests
from datetime import datetime

# Load environment
load_dotenv()

# === Konfigurasi Gemini ===
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")

# === Konfigurasi OpenRouter ===
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")

# Logging
logging.basicConfig(level=logging.INFO)

# Flask Setup
app = Flask(__name__)
CORS(app)

# Load data kampus
with open("trisakti_info.json", "r", encoding="utf-8") as f:
    campus_data = json.load(f)

# Simpan histori chat
CHAT_HISTORY_PATH = "chat_history.json"
if not os.path.exists(CHAT_HISTORY_PATH):
    with open(CHAT_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

# Fungsi pencocokan keyword
def find_category(user_input):
    for category, keywords in campus_data.get("faq_keywords", {}).items():
        for keyword in keywords:
            if keyword.lower() in user_input.lower():
                return category
    return None

# Fungsi ambil jawaban dari JSON
def get_answer_by_category(category):
    if category == "alamat":
        return f"Kampus Trisakti School of Multimedia beralamat di {campus_data['address']}."
    elif category == "kontak":
        kontak = campus_data["kontak"]
        return (
            f"""Berikut informasi kontak resmi Trisakti School of Multimedia:\n
Alamat: {campus_data['address']}
Telepon: {', '.join(kontak['phone'])}
Email: {kontak['email']}
WhatsApp: {kontak['whatsapp']}
Jam Operasional: {kontak['office_hours']}
Instagram: {kontak['social_media']['instagram']}
Facebook: {kontak['social_media']['facebook']}"""
        )
    elif category == "prodi":
        prodi = [f"- {p['name']}" for p in campus_data["programs"]]
        return "Berikut program studi yang tersedia:\n" + "\n".join(prodi)
    elif category == "beasiswa":
        beasiswa = [f"- {b['name']}: {b['description']}" for b in campus_data["beasiswa"]]
        return "Kami menyediakan beberapa beasiswa, antara lain:\n" + "\n".join(beasiswa)
    elif category == "pendaftaran":
        return (
            f"Pendaftaran dilakukan secara online melalui: {campus_data['registration_link']}\n"
            f"Proses: {campus_data['registration_details']['process']}"
        )
    elif category == "fasilitas":
        return "Fasilitas kampus kami meliputi:\n- " + "\n- ".join(campus_data["facilities"])
    elif category == "akreditasi":
        akred = campus_data["accreditation"]
        return f"Akreditasi institusi: {akred['overall']}\nProgram Studi:\n" + "\n".join([f"- {k}: {v}" for k, v in akred["programs"].items()])
    elif category == "sejarah":
        return campus_data["history"]
    elif category == "jadwal":
        sem1 = campus_data["academic_calendar"]["semester_1_2025"]
        sem2 = campus_data["academic_calendar"]["semester_2_2025"]
        return (
            f"Semester 1 dimulai {sem1['start']} hingga {sem1['end']}.\n"
            f"Libur: {', '.join(sem1['holidays'])}\n\n"
            f"Semester 2 dimulai {sem2['start']} hingga {sem2['end']}.\n"
            f"Libur: {', '.join(sem2['holidays'])}"
        )
    elif category == "testimoni":
        return "\n\n".join([f"{t['name']} ({t['program']}): {t['testimonial']}" for t in campus_data["alumni_testimonials"]])
    elif category == "keunggulan":
        return campus_data["why_trisakti"]
    elif category == "berita":
        return "\n\n".join([f"{b['title']} ({b['date']}): {b['description']}" for b in campus_data["news"]])
    elif category == "identitas_kampus":
        return f"Trisakti School of Multimedia (TMM) adalah perguruan tinggi media komunikasi yang berdiri sejak tahun {campus_data['foundation_year']}."
    else:
        return None

# Fallback ke OpenRouter jika Gemini gagal
def fallback_openrouter(prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": "Jawab dengan bahasa Indonesia yang sopan dan profesional."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()['choices'][0]['message']['content']
    else:
        return "Mohon maaf, saat ini kami tidak dapat menjawab pertanyaan Anda. Silakan coba beberapa saat lagi."

# Route utama
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_input = data.get("message", "")
        category = find_category(user_input)

        if category:
            response = get_answer_by_category(category)
        else:
            try:
                model = genai.GenerativeModel(GEMINI_MODEL)
                chat = model.start_chat()
                gemini_response = chat.send_message(user_input)
                response = gemini_response.text
            except google_ex.GoogleAPIError as e:
                logging.error("Gemini error: %s", e)
                response = fallback_openrouter(user_input)

        save_chat(user_input, response)
        return jsonify({"response": response})

    except Exception as e:
        logging.exception("Chat error")
        return jsonify({"response": "Terjadi kesalahan. Silakan coba kembali."}), 500

# Simpan riwayat chat
def save_chat(user_input, response):
    chat_data = {
        "timestamp": datetime.now().isoformat(),
        "user": user_input,
        "bot": response
    }
    with open(CHAT_HISTORY_PATH, "r+", encoding="utf-8") as f:
        data = json.load(f)
        data.append(chat_data)
        f.seek(0)
        json.dump(data, f, ensure_ascii=False, indent=2)

# Run server
if __name__ == "__main__":
    app.run(debug=True)