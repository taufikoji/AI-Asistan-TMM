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
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah asisten AI resmi kampus Trisakti School of Multimedia (STMKT). "
                        "Jawabanmu harus mengutamakan dan memprioritaskan informasi dari situs resmi https://trisaktimultimedia.ac.id. "
                        "Jika tidak yakin, katakan 'Silakan cek langsung ke situs resmi'. "
                        "Jangan gunakan singkatan lain selain STMKT untuk nama kampus. "
                        "Jawablah dalam bahasa Indonesia yang ramah dan sopan."
                    )
                },
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

    # Respon sapaan
    sapaan = ["halo", "hai", "hi", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
    if pesan in sapaan:
        return "Halo! Saya adalah asisten AI dari STMK Trisakti. Ada yang bisa saya bantu? 😊"

    # Respon ucapan terima kasih
    if any(kata in pesan for kata in ["terima kasih", "makasih", "thanks", "thank you"]):
        pantun = random.choice(pantun_daftar)
        return f"Sama-sama! Senang bisa membantu kamu! 🙌\n\n{pantun}"

    # Jawaban dari data JSON
    if "alamat" in pesan:
        alamat = data_kampus.get("address")
        if isinstance(alamat, dict):
            return f"{alamat['value']}\n📍 Sumber: {alamat.get('source', '')}"
        return alamat or "Alamat belum tersedia."

    elif "nomor" in pesan or "telepon" in pesan:
        telepon = data_kampus.get("phone", [])
        return f"Nomor telepon: {', '.join(telepon)}" if telepon else "Nomor telepon belum tersedia."

    elif "whatsapp" in pesan or "wa" in pesan:
        wa = data_kampus["contact"]["whatsapp"]
        if isinstance(wa, dict):
            return f"WhatsApp: {wa['value']}\n📍 Sumber: {wa.get('source', '')}"
        return f"WhatsApp: {wa}"

    elif "email" in pesan:
        email = data_kampus["contact"]["email"]
        if isinstance(email, dict):
            return f"Email: {email['value']}\n📍 Sumber: {email.get('source', '')}"
        return f"Email: {email}"

    elif "visi" in pesan:
        return data_kampus.get("vision", "Visi belum tersedia.")

    elif "misi" in pesan:
        return "\n".join(data_kampus.get("mission", []))

    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi yang tersedia:\n" + "\n".join(data_kampus.get("programs", []))

    elif "fasilitas" in pesan:
        return "Fasilitas kampus:\n" + "\n".join(data_kampus.get("facilities", []))

    elif "akreditasi" in pesan:
        akreditasi = data_kampus.get("accreditation", {})
        prodi = akreditasi.get("programs", {})
        prodi_list = "\n".join([f"- {k}: {v}" for k, v in prodi.items()])
        return f"Akreditasi keseluruhan: {akreditasi.get('overall', 'Belum tersedia')}\n{prodi_list}"

    elif "nilai" in pesan or "value" in pesan:
        return "Nilai kampus: " + ", ".join(data_kampus.get("values", []))

    elif "sejarah" in pesan or "berdiri" in pesan:
        return data_kampus.get("history", "Data sejarah tidak tersedia.")

    return None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)