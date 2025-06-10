import os
import json
import random
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Muat data kampus dari file JSON
with open("data_kampus.json", "r", encoding="utf-8") as f:
    data_kampus = json.load(f)

# Kumpulan pantun ajakan mendaftar
pantun_daftar = [
    "Jalan-jalan ke Kota Bekasi,\nJangan lupa beli roti.\nKalau mau jadi insan kreatif dan berprestasi,\nYuk daftar di STMK Trisakti! 🎓✨",
    "Ke pasar beli tomat dan cabai,\nPulang bawa sepiring nasi.\nKalau kamu ingin masa depan cerah dan gemilang,\nSTMK Trisakti pilihan pasti! 💡🎓",
    "Burung nuri hinggap di dahan,\nBerkicau riang di pagi hari.\nKalau kamu cari kampus kekinian,\nSTMK Trisakti tempatnya berseri! 🔥🖥️",
    "Naik sepeda keliling taman,\nSambil minum es kelapa muda.\nYuk kuliah di kampus multimedia zaman sekarang,\nSTMK Trisakti tempat ilmu dan budaya! 🎬🎨"
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message")

        # Cek apakah jawaban tersedia di data lokal JSON
        jawaban_lokal = cek_data_kampus(user_msg)
        if jawaban_lokal:
            return jsonify({"reply": jawaban_lokal})

        # Jika tidak ditemukan, lanjut ke model AI (DeepSeek R1)
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://trisaktimultimedia.ac.id",
            "X-Title": "STMK Chatbot"
        }

        data = {
            "model": "deepseek/deepseek-r1-0528:free",
            "messages": [
                {"role": "system", "content": "Kamu adalah asisten AI kampus Trisakti School of Multimedia (STMKT) yang beralamat di situs trisaktimultimedia.ac.id. Jawablah dalam bahasa Indonesia."},
                {"role": "user", "content": user_msg}
            ]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": f"Gagal dari OpenRouter: {response.text}"}), 500

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan: {str(e)}"}), 500

def cek_data_kampus(pesan):
    """Mencocokkan pertanyaan dengan data JSON kampus atau merespons sapaan/ucapan terima kasih."""
    pesan = pesan.lower().strip()

    # Respon jika hanya sapaan
    sapaan = ["halo", "hai", "hi", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
    if pesan in sapaan:
        return "Halo! Saya adalah asisten AI dari STMK Trisakti. Ada yang bisa saya bantu? 😊"

    # Respon jika pengunjung berterima kasih
    if any(kata in pesan for kata in ["terima kasih", "makasih", "thanks", "thank you"]):
        pantun = random.choice(pantun_daftar)
        return f"Sama-sama! Senang bisa membantu kamu! 🙌\n\n{pantun}"

    if "alamat" in pesan:
        return data_kampus.get("address", "Alamat belum tersedia.")
    elif "nomor" in pesan or "telepon" in pesan:
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))}"
    elif "whatsapp" in pesan or "wa" in pesan:
        return f"WhatsApp kampus: {data_kampus['contact']['whatsapp']}"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['contact']['email']}"
    elif "visi" in pesan:
        return data_kampus["vision"]
    elif "misi" in pesan:
        return "\n".join(data_kampus["mission"])
    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi yang tersedia:\n" + "\n".join(data_kampus["programs"])
    elif "fasilitas" in pesan:
        return "Fasilitas kampus:\n" + "\n".join(data_kampus["facilities"])
    elif "akreditasi" in pesan:
        akreditasi = data_kampus["accreditation"]
        prodi = "\n".join([f"- {k}: {v}" for k, v in akreditasi["programs"].items()])
        return f"Akreditasi keseluruhan: {akreditasi['overall']}\n{prodi}"
    elif "nilai" in pesan or "value" in pesan:
        return "Nilai kampus: " + ", ".join(data_kampus.get("values", []))
    elif "sejarah" in pesan or "berdiri" in pesan:
        return data_kampus.get("history", "Data sejarah tidak tersedia.")

    return None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)