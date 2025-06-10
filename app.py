import os
import json
import random
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Load data kampus dari JSON
with open("data_kampus.json", "r", encoding="utf-8") as f:
    data_kampus = json.load(f)

pantun_daftar = [
    "Naik kereta ke Pasar Minggu,\nJangan lupa beli mangga.\nYuk daftar di STMK Trisakti,\nKampusnya anak kreatif semua! 🎨🎓",
    "Burung camar terbang ke barat,\nDi pantai bersinar cahaya mentari.\nSTMK Trisakti pilihan tepat,\nMasa depan cerah menanti! 🌟📚",
    "Ke pasar beli pepaya,\nPulangnya mampir ke warung mie.\nSTMK Trisakti kampus budaya,\nAyo daftar sekarang juga, jangan nanti! ✨📹"
]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message").strip().lower()

        # Cek jawaban dari data lokal (kampus)
        jawaban_lokal = cek_data_kampus(user_msg)
        if jawaban_lokal:
            return jsonify({"reply": jawaban_lokal})

        # Pertanyaan ringan → AI
        if is_ringan(user_msg):
            return jsonify({"reply": ai_respon_ringan(user_msg)})

        # Pertanyaan akademik → AI
        if is_akademik(user_msg):
            ai_jawaban = tanya_ai(user_msg)
            return jsonify({"reply": ai_jawaban})

        # Pertanyaan lain → tolak dengan sopan
        return jsonify({
            "reply": "Maaf, saya hanya dapat menjawab pertanyaan seputar STMK Trisakti dan pendidikan. "
                     "Silakan kunjungi situs resmi kami di https://trisaktimultimedia.ac.id 😊"
        })

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan: {str(e)}"}), 500

def cek_data_kampus(pesan):
    if "alamat" in pesan:
        return data_kampus.get("address", "Alamat belum tersedia.")
    elif "nomor" in pesan or "telepon" in pesan:
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))}"
    elif "whatsapp" in pesan or "wa" in pesan:
        return f"WhatsApp kampus: {data_kampus['contact']['whatsapp']}"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['contact']['email']}"
    elif "visi" in pesan:
        return data_kampus.get("vision", "Visi belum tersedia.")
    elif "misi" in pesan:
        return "\n".join(data_kampus.get("mission", []))
    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi:\n" + "\n".join(data_kampus.get("programs", []))
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
        return data_kampus.get("history", "Sejarah belum tersedia.")
    elif "tentang kampus" in pesan:
        return (
            "STMK Trisakti adalah kampus multimedia modern dengan fokus pada teknologi, desain, dan komunikasi. "
            "Kunjungi situs resmi kami untuk informasi lengkap: https://trisaktimultimedia.ac.id"
        )
    return None

def is_ringan(pesan):
    sapaan = ["halo", "hai", "hi", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam"]
    ucapan_terima_kasih = ["terima kasih", "makasih", "thanks", "thank you"]
    return pesan in sapaan or any(kata in pesan for kata in ucapan_terima_kasih)

def ai_respon_ringan(pesan):
    if any(kata in pesan for kata in ["terima kasih", "makasih", "thanks", "thank you"]):
        pantun = random.choice(pantun_daftar)
        return f"Sama-sama! Semoga harimu menyenangkan! 🙌\n\n{pantun}"
    return "Halo! Saya asisten AI dari STMK Trisakti. Silakan tanya apa pun tentang kampus atau pendidikan 😊"

def is_akademik(pesan):
    # Deteksi kata kunci terkait pendidikan umum
    topik = ["apa itu", "bagaimana cara", "pengertian", "fungsi", "contoh", "manfaat", "tujuan", "perbedaan", "kuliah", "skripsi", "dosen", "mata kuliah", "belajar"]
    return any(k in pesan for k in topik)

def tanya_ai(pesan):
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
                    "Kamu adalah asisten AI ramah yang menjawab pertanyaan umum seputar dunia pendidikan dan akademik. "
                    "Jawaban harus informatif, akurat, dan mudah dimengerti oleh pelajar atau calon mahasiswa."
                )
            },
            {"role": "user", "content": pesan}
        ]
    }

    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        return f"Maaf, terjadi kesalahan saat menghubungi AI. ({response.status_code})"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)