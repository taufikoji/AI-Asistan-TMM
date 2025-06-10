import os
import json
import random
from flask import Flask, render_template, request, jsonify, session
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key_here")  # Ganti dengan kunci rahasia yang aman

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Muat data kampus dari file JSON
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
    # Inisialisasi sesi jika belum ada
    if "ai_mode" not in session:
        session["ai_mode"] = False

    try:
        user_msg = request.json.get("message").strip().lower()

        # Cek apakah pengguna ingin masuk/keluar dari mode AI
        if any(k in user_msg for k in ["bicara dengan ai", "ai bantu saya", "ai jawab"]):
            session["ai_mode"] = True
            return jsonify({"reply": "Sekarang kamu berbicara dengan AI! 😊 Saya akan membantu dengan pertanyaan apa pun tentang STMK Trisakti atau topik akademik. Ketik 'keluar dari ai' untuk kembali ke mode biasa. Apa yang ingin kamu tanyakan?"})
        elif "keluar dari ai" in user_msg:
            session["ai_mode"] = False
            keywords = "Kata kunci yang bisa dicoba: alamat, jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, fokus teknologi, lebih lengkap."
            return jsonify({"reply": f"Kamu telah keluar dari mode AI. Kembali ke mode biasa! 😊 {keywords} \n\n{random.choice(pantun_daftar)}"})

        # Jika dalam mode AI, semua pertanyaan langsung ke AI
        if session["ai_mode"]:
            ai_reply = ai_jawab(user_msg)
            # Validasi alamat jika pertanyaan terkait lokasi
            if "lokasi" in user_msg or "alamat" in user_msg:
                if data_kampus["address"] not in ai_reply:
                    ai_reply = f"Alamat resmi STMK Trisakti: {data_kampus['address']}\n📍 Sumber: {data_kampus['website']}\nMaaf jika ada info lain yang kurang tepat, AI mungkin salah menebak. Coba tanyakan lagi atau ketik 'keluar dari ai'!"
            if is_jawaban_relevan(ai_reply, user_msg):
                return jsonify({"reply": ai_reply})
            else:
                return jsonify({"reply": "Maaf, AI tidak bisa menjawab itu dengan baik. Coba tanyakan tentang STMK Trisakti atau topik akademik lain, atau ketik 'keluar dari ai' untuk kembali. 😊"})

        # Cek apakah pertanyaan cocok dengan data kampus
        jawaban_lokal = cek_data_kampus(user_msg)
        if jawaban_lokal:
            # Tambahkan pantun secara acak untuk respons lokal (20% kemungkinan)
            if random.random() < 0.2:
                jawaban_lokal += f"\n\n{random.choice(pantun_daftar)}"
            return jsonify({"reply": jawaban_lokal})

        # Cek apakah sapaan ringan
        if is_ringan(user_msg):
            keywords = "Kata kunci yang bisa dicoba: alamat, jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, fokus teknologi, lebih lengkap. Atau ketik 'bicara dengan ai' untuk berinteraksi langsung dengan AI!"
            return jsonify({"reply": f"Halo! Selamat datang di chatbot STMK Trisakti! 😊 Sepertinya kamu ingin bertanya? {keywords} \n\n{random.choice(pantun_daftar)}"})

        # Cek apakah pertanyaan akademik
        if is_akademik(user_msg):
            ai_reply = ai_jawab(user_msg)
            # Validasi alamat jika pertanyaan terkait lokasi
            if "lokasi" in user_msg or "alamat" in user_msg:
                if data_kampus["address"] not in ai_reply:
                    ai_reply = f"Alamat resmi STMK Trisakti: {data_kampus['address']}\n📍 Sumber: {data_kampus['website']}\nMaaf jika ada info lain yang kurang tepat, AI mungkin salah menebak. Coba tanyakan lagi atau ketik 'bicara dengan ai'!"
            if is_jawaban_relevan(ai_reply, user_msg):
                return jsonify({"reply": ai_reply})
            else:
                keywords = "Coba kata kunci seperti: jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, atau fokus teknologi. Atau ketik 'bicara dengan ai' untuk mode AI penuh!"
                return jsonify({"reply": f"Maaf, sepertinya pertanyaanmu kurang relevan. {keywords} Tanyakan tentang STMK Trisakti atau topik akademik lainnya! 😊"})

        # Jika tidak relevan
        keywords = "Coba kata kunci seperti: alamat, jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, fokus teknologi, atau ketik 'lebih lengkap' atau 'bicara dengan ai'."
        return jsonify({"reply": f"Maaf, saya agak bingung dengan pertanyaanmu. Saya hanya bisa membantu seputar STMK Trisakti atau topik akademik. {keywords} Kunjungi https://trisaktimultimedia.ac.id! 😊 \n\n{random.choice(pantun_daftar)}"})

    except Exception as e:
        return jsonify({"reply": f"Ups, ada masalah teknis: {str(e)}. Coba lagi nanti atau kunjungi https://trisaktimultimedia.ac.id untuk info lebih lanjut! 😊"}), 500

def cek_data_kampus(pesan):
    # Prioritaskan kata kunci yang lebih spesifik
    if "alamat" in pesan:
        return f"Alamat STMK Trisakti: {data_kampus['address']}\n📍 Sumber: {data_kampus['website']} (Kata kunci lain: jurusan, fasilitas, whatsapp, atau ketik 'bicara dengan ai' untuk AI)"
    elif any(k in pesan for k in ["tentang kampus", "informasi kampus", "apa itu stmk"]):
        return (
            "STMK Trisakti (Trisakti School of Multimedia) adalah perguruan tinggi yang fokus pada media dan teknologi kreatif, mempersiapkan lulusan untuk industri digital.\n"
            f"📌 Jurusan: {', '.join(data_kampus['programs'])}\n"
            f"📌 Fasilitas: {', '.join(data_kampus['facilities'][:2])} (dan lainnya, gunakan kata kunci 'fasilitas' untuk detail!)\n"
            "📌 Website resmi: https://trisaktimultimedia.ac.id\n"
            "Mau tahu lebih banyak? Coba kata kunci: visi, misi, atau jurusan, atau ketik 'bicara dengan ai'! 😊"
        )
    elif any(k in pesan for k in ["nomor telepon", "telepon", "kontak telepon"]):
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))} (Kata kunci lain: whatsapp, email, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["whatsapp", "wa"]):
        return f"WhatsApp kampus: {data_kampus['contact']['whatsapp']}\nSilakan hubungi untuk info pendaftaran atau pertanyaan lainnya! (Kata kunci lain: telepon, email, atau 'bicara dengan ai')"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['contact']['email']} (Kata kunci lain: whatsapp, telepon, atau 'bicara dengan ai')"
    elif "visi" in pesan:
        return f"Visi STMK Trisakti: {data_kampus['vision']} (Kata kunci lain: misi, jurusan, atau 'bicara dengan ai')"
    elif "misi" in pesan:
        return "Misi STMK Trisakti:\n" + "\n".join(data_kampus["mission"]) + " (Kata kunci lain: visi, fasilitas, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi di STMK Trisakti:\n" + "\n".join(data_kampus["programs"]) + " (Kata kunci lain: fasilitas, akreditasi, atau 'bicara dengan ai')"
    elif "fasilitas" in pesan:
        return "Fasilitas kampus STMK Trisakti:\n" + "\n".join(data_kampus["facilities"]) + " (Kata kunci lain: jurusan, laboratorium, atau 'bicara dengan ai')"
    elif "akreditasi" in pesan:
        akreditasi = data_kampus["accreditation"]
        prodi = "\n".join([f"- {k}: {v}" for k, v in akreditasi["programs"].items()])
        return f"Akreditasi keseluruhan: {akreditasi['overall']}\nProgram studi:\n{prodi} (Kata kunci lain: jurusan, visi, atau 'bicara dengan ai')"
    elif "nilai" in pesan or "value" in pesan:
        return "Nilai-nilai STMK Trisakti: " + ", ".join(data_kampus.get("values", [])) + " (Kata kunci lain: visi, misi, atau 'bicara dengan ai')"
    elif "sejarah" in pesan or "berdiri" in pesan:
        return data_kampus.get("history", "Informasi sejarah tidak tersedia. Kunjungi https://trisaktimultimedia.ac.id untuk detail lebih lanjut.") + " (Kata kunci lain: visi, jurusan, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["mahasiswa", "siswa"]):
        return (
            "Mahasiswa STMK Trisakti belajar di lingkungan kreatif dengan fokus pada multimedia, desain, dan teknologi digital. "
            "Mau tahu lebih banyak? Coba kata kunci: program studi, fasilitas, atau fokus teknologi, atau ketik 'bicara dengan ai'! Tanya saya atau cek https://trisaktimultimedia.ac.id!"
        )
    elif any(k in pesan for k in ["kerja sama", "kolaborasi"]):
        return "\n".join([f"- {c['partner']}: {c['description']} (Tanggal: {c['date']})" for c in data_kampus.get("collaborations", [])]) + " (Kata kunci lain: jurusan, fasilitas, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["fokus teknologi", "teknologi fokus"]):
        return "Fokus teknologi STMK Trisakti: " + ", ".join(data_kampus.get("focus_areas", [])) + " (Kata kunci lain: jurusan, misi, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["lebih lengkap", "detail", "info lebih"]):
        return (
            "Tentu! Kamu bisa tanyakan lebih detail tentang:\n- Jurusan/Program Studi (gunakan: jurusan)\n- Fasilitas Kampus (gunakan: fasilitas)\n- Visi dan Misi (gunakan: visi, misi)\n- Kontak (gunakan: whatsapp, telepon, email)\n- Kerja Sama (gunakan: kerja sama)\n- Fokus Teknologi (gunakan: fokus teknologi)\n"
            "Atau ketik 'bicara dengan ai' untuk interaksi langsung dengan AI! Coba tanyakan salah satunya, ya! 😊\n\n{random.choice(pantun_daftar)}"
        )
    return None

def is_ringan(pesan):
    sapaan = ["halo", "hai", "hi", "assalamualaikum", "selamat pagi", "selamat siang", "selamat sore", "selamat malam", "saya ingin bertanya", "ucanda", "saya ingin bicara"]
    ucapan_terima_kasih = ["terima kasih", "makasih", "thanks", "thank you"]
    return pesan in sapaan or any(kata in pesan for kata in ucapan_terima_kasih)

def is_akademik(pesan):
    kata_kunci = [
        "apa itu", "perbedaan", "contoh", "penjelasan", "skripsi", "kuliah", 
        "dosen", "kampus", "pendidikan", "akademik", "belajar", "kurikulum", 
        "matakuliah", "desain", "multimedia", "teknologi", "digital", "branding", 
        "kreatif", "internet of things", "artificial intelligence", "media"
    ]
    return any(k in pesan for k in kata_kunci)

def is_jawaban_relevan(jawaban, pesan):
    kata_kunci_relevan = [
        "trisakti", "stmk", "multimedia", "kampus", "pendidikan", "akademik", 
        "kuliah", "desain", "teknologi", "digital", "branding", "kreatif"
    ]
    jawaban_lower = jawaban.lower()
    return any(kata in jawaban_lower for kata in kata_kunci_relevan) or any(kata in pesan for kata in kata_kunci_relevan)

def ai_jawab(pesan):
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
                    "Kamu adalah asisten AI resmi dari STMK Trisakti. Hanya jawab pertanyaan terkait kampus STMK Trisakti atau topik akademik seperti multimedia, desain, teknologi kreatif, atau pendidikan tinggi. "
                    "Gunakan data dari file data_kampus.json sebagai acuan utama untuk informasi seperti alamat, jurusan, dan fasilitas. Jika informasi tidak tersedia di data_kampus.json, katakan bahwa kamu tidak bisa menjawab dan arahkan ke website resmi. "
                    "Gunakan bahasa Indonesia yang sopan, jelas, ramah, dan profesional. Jangan berikan jawaban spekulatif atau di luar topik. "
                    "Sertakan nada interaktif dan kreatif, misalnya dengan mengajak pengguna untuk bertanya lebih lanjut menggunakan kata kunci seperti: jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, atau fokus teknologi. Jika pengguna ingin keluar, sarankan 'keluar dari ai'."
                )
            },
            {"role": "user", "content": pesan}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()  # Raise an error for bad status codes
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException:
        return "Mohon maaf, saya sedang kesulitan menghubungi server. Silakan coba lagi nanti atau kunjungi https://trisaktimultimedia.ac.id untuk info lebih lanjut! 😊"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)