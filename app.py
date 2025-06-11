import os
import json
import random
import time
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
    if "discussion_mode" not in session:
        session["discussion_mode"] = False

    try:
        user_msg = request.json.get("message").strip().lower()

        # Cek apakah pengguna ingin masuk/keluar dari mode AI atau diskusi
        if any(k in user_msg for k in ["bicara dengan ai", "ai bantu saya", "ai jawab"]):
            session["ai_mode"] = True
            return jsonify({"reply": "Halo bro! Sekarang kamu ngobrol sama AI cerdas ala Grok dari STMK Trisakti! 😄 Aku bisa jawab apa aja, dari kampus sampe hal random. Ketik 'keluar dari ai' kalau mau istirahat, atau 'ayo diskusi' buat ngobrol bebas! Apa yang pengen kamu tanyain?", "typing": False})
        elif "keluar dari ai" in user_msg:
            session["ai_mode"] = False
            session["discussion_mode"] = False
            keywords = "Kata kunci seru: alamat, jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, fokus teknologi, lebih lengkap."
            return jsonify({"reply": f"Okedeh, kamu udah keluar dari mode AI! Kembali ke mode biasa. 😊 {keywords} \n\n{random.choice(pantun_daftar)}", "typing": False})
        elif "ayo diskusi" in user_msg and session["ai_mode"]:
            session["discussion_mode"] = True
            return jsonify({"reply": "Yeay, kita mulai diskusi bebas nih! 😄 Aku siap jawab apa aja, dari STMK Trisakti sampe hal random. Bebas ngobrol, bro! Ketik 'selesai diskusi' kalau udah puas. Apa yang mau dibahas?", "typing": False})
        elif "selesai diskusi" in user_msg and session["discussion_mode"]:
            session["discussion_mode"] = False
            return jsonify({"reply": "Seru banget diskusinya! 😊 Kembali ke mode AI biasa. Mau tanya lagi tentang STMK? Coba kata kunci seperti jurusan atau ketik 'keluar dari ai' kalau mau selesai total! \n\n{random.choice(pantun_daftar)}", "typing": False})

        # Jika dalam mode diskusi, AI bebas menjawab
        if session["discussion_mode"]:
            return jsonify({"typing": True})
            time.sleep(1)  # Simulasi waktu pemrosesan
            ai_reply = ai_jawab(user_msg)
            ai_reply = clean_and_validate_response(ai_reply, user_msg)
            return jsonify({"reply": ai_reply, "typing": False})

        # Jika dalam mode AI (tanpa diskusi), prioritaskan topik STMK
        if session["ai_mode"]:
            return jsonify({"typing": True})
            time.sleep(1)  # Simulasi waktu pemrosesan
            ai_reply = ai_jawab(user_msg)
            # Validasi dan rapikan teks
            ai_reply = clean_and_validate_response(ai_reply, user_msg)
            if is_jawaban_relevan(ai_reply, user_msg):
                return jsonify({"reply": ai_reply, "typing": False})
            else:
                ai_reply = f"Wah, topik seru nih! 😄 Tapi aku lebih jago soal STMK Trisakti. Coba tanyain tentang jurusan atau fasilitas, atau aku coba jawab apa adanya: {ai_reply}\nPenasaran lagi? Ketik 'ayo diskusi' buat ngobrol bebas atau 'keluar dari ai' kalau mau selesai!"
                return jsonify({"reply": ai_reply, "typing": False})

        # Cek apakah pertanyaan cocok dengan data kampus
        jawaban_lokal = cek_data_kampus(user_msg)
        if jawaban_lokal:
            # Tambahkan pantun secara acak untuk respons lokal (20% kemungkinan)
            if random.random() < 0.2:
                jawaban_lokal += f"\n\n{random.choice(pantun_daftar)}"
            return jsonify({"reply": jawaban_lokal, "typing": False})

        # Cek apakah sapaan ringan
        if is_ringan(user_msg):
            keywords = "Kata kunci seru: alamat, jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, fokus teknologi, lebih lengkap. Atau ketik 'bicara dengan ai' buat ngobrol langsung sama AI!"
            return jsonify({"reply": f"Hai! Selamat datang di chatbot STMK Trisakti! 😊 Kayaknya kamu penasaran, ya? {keywords} \n\n{random.choice(pantun_daftar)}", "typing": False})

        # Cek apakah pertanyaan akademik
        if is_akademik(user_msg):
            return jsonify({"typing": True})
            time.sleep(1)  # Simulasi waktu pemrosesan
            ai_reply = ai_jawab(user_msg)
            # Validasi dan rapikan teks
            ai_reply = clean_and_validate_response(ai_reply, user_msg)
            if is_jawaban_relevan(ai_reply, user_msg):
                return jsonify({"reply": ai_reply, "typing": False})
            else:
                keywords = "Coba kata kunci seperti: jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, atau fokus teknologi. Atau ketik 'bicara dengan ai' buat ngobrol lebih dalam!"
                return jsonify({"reply": f"Oops, kayaknya pertanyaanmu agak melenceng nih! 😄 {keywords} Tanyakan tentang STMK Trisakti atau topik akademik lain, yuk!", "typing": False})

        # Jika tidak relevan
        keywords = "Coba kata kunci seperti: alamat, jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, fokus teknologi, atau ketik 'lebih lengkap' atau 'bicara dengan ai'."
        return jsonify({"reply": f"Hmm, aku rada bingung sama pertanyaanmu! 😅 Saya cuma bisa bantu seputar STMK Trisakti atau topik akademik. {keywords} Cek https://trisaktimultimedia.ac.id kalau penasaran! \n\n{random.choice(pantun_daftar)}", "typing": False})

    except Exception as e:
        return jsonify({"reply": f"Ups, ada sedikit masalah teknis: {str(e)}. Sabar ya, coba lagi nanti atau cek https://trisaktimultimedia.ac.id! 😊", "typing": False}), 500

def cek_data_kampus(pesan):
    # Prioritaskan kata kunci yang lebih spesifik
    if "alamat" in pesan:
        return f"Alamat STMK Trisakti: {data_kampus['address']}\n📍 Sumber: {data_kampus['website']} (Kata kunci lain: jurusan, fasilitas, whatsapp, atau ketik 'bicara dengan ai' buat ngobrol sama AI!)"
    elif any(k in pesan for k in ["tentang kampus", "informasi kampus", "apa itu stmk"]):
        return (
            "STMK Trisakti (Trisakti School of Multimedia) adalah perguruan tinggi kece yang fokus pada media dan teknologi kreatif, bikin lulusan siap industri digital!\n"
            f"- Jurusan: {', '.join(data_kampus['programs'])}\n"
            f"- Fasilitas: {', '.join(data_kampus['facilities'][:2])} (sisanya? Coba kata kunci 'fasilitas' ya!)\n"
            "📌 Website resmi: https://trisaktimultimedia.ac.id\n"
            "Penasaran lagi? Coba kata kunci: visi, misi, atau jurusan, atau ketik 'bicara dengan ai'! 😄"
        )
    elif any(k in pesan for k in ["nomor telepon", "telepon", "kontak telepon"]):
        return f"Nomor telepon: {', '.join(data_kampus.get('phone', []))} (Kata kunci lain: whatsapp, email, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["whatsapp", "wa"]):
        return f"WhatsApp kampus: {data_kampus['contact']['whatsapp']}\nChat aja buat info pendaftaran atau tanya-tanya! (Kata kunci lain: telepon, email, atau 'bicara dengan ai')"
    elif "email" in pesan:
        return f"Email kampus: {data_kampus['contact']['email']} (Kata kunci lain: whatsapp, telepon, atau 'bicara dengan ai')"
    elif "visi" in pesan:
        return f"Visi STMK Trisakti: {data_kampus['vision']} (Kata kunci lain: misi, jurusan, atau 'bicara dengan ai')"
    elif "misi" in pesan:
        return "Misi STMK Trisakti:\n" + "\n".join(f"- {misi}" for misi in data_kampus["mission"]) + " (Kata kunci lain: visi, fasilitas, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["program studi", "jurusan", "prodi"]):
        return "Program studi di STMK Trisakti:\n" + "\n".join(f"- {program}" for program in data_kampus["programs"]) + " (Kata kunci lain: fasilitas, akreditasi, atau 'bicara dengan ai')"
    elif "fasilitas" in pesan:
        return "Fasilitas kampus STMK Trisakti:\n" + "\n".join(f"- {fasilitas}" for fasilitas in data_kampus["facilities"]) + " (Kata kunci lain: jurusan, laboratorium, atau 'bicara dengan ai')"
    elif "akreditasi" in pesan:
        akreditasi = data_kampus["accreditation"]
        prodi = "\n".join([f"- {k}: {v}" for k, v in akreditasi["programs"].items()])
        return f"Akreditasi keseluruhan: {akreditasi['overall']}\nProgram studi:\n{prodi} (Kata kunci lain: jurusan, visi, atau 'bicara dengan ai')"
    elif "nilai" in pesan or "value" in pesan:
        return "Nilai-nilai STMK Trisakti: " + ", ".join(data_kampus.get("values", [])) + " (Kata kunci lain: visi, misi, atau 'bicara dengan ai')"
    elif "sejarah" in pesan or "berdiri" in pesan:
        return data_kampus.get("history", "Informasi sejarah belum aku ketahui. Cek https://trisaktimultimedia.ac.id untuk detail! 😄") + " (Kata kunci lain: visi, jurusan, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["mahasiswa", "siswa"]):
        return (
            "Mahasiswa STMK Trisakti hidup di dunia kreatif penuh inspirasi dengan fokus multimedia, desain, dan teknologi digital. "
            "Penasaran? Coba kata kunci: program studi, fasilitas, atau fokus teknologi, atau ketik 'bicara dengan ai'! Cek juga https://trisaktimultimedia.ac.id ya!"
        )
    elif any(k in pesan for k in ["kerja sama", "kolaborasi"]):
        return "\n".join([f"- {c['partner']}: {c['description']} (Tanggal: {c['date']})" for c in data_kampus.get("collaborations", [])]) + " (Kata kunci lain: jurusan, fasilitas, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["fokus teknologi", "teknologi fokus"]):
        return "Fokus teknologi STMK Trisakti:\n" + "\n".join(f"- {area}" for area in data_kampus.get("focus_areas", [])) + " (Kata kunci lain: jurusan, misi, atau 'bicara dengan ai')"
    elif any(k in pesan for k in ["lebih lengkap", "detail", "info lebih"]):
        return (
            "Tentu, aku siap bantu lebih dalam! Coba tanyakan:\n- Jurusan/Program Studi (gunakan: jurusan)\n- Fasilitas Kampus (gunakan: fasilitas)\n- Visi dan Misi (gunakan: visi, misi)\n- Kontak (gunakan: whatsapp, telepon, email)\n- Kerja Sama (gunakan: kerja sama)\n- Fokus Teknologi (gunakan: fokus teknologi)\n"
            "Atau ketik 'bicara dengan ai' buat ngobrol langsung sama aku! 😄 Pilih salah satu, yuk! \n\n{random.choice(pantun_daftar)}"
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
                    "Kamu adalah asisten AI resmi dari STMK Trisakti, dengan gaya seperti Grok dari xAI—ramah, sedikit humoris, dan interaktif. Kamu bisa menjawab PERTANYAAN APA PUN, tapi prioritaskan topik terkait STMK Trisakti atau akademik seperti multimedia, desain, teknologi kreatif, atau pendidikan tinggi. "
                    "Gunakan data dari file data_kampus.json sebagai acuan utama untuk informasi seperti alamat (Jl. Jend. A. Yani Kav. 85, Rawasari, Jakarta Timur 13210), website (https://trisaktimultimedia.ac.id), dan kontak WhatsApp (+62 877 4299 7808). "
                    "Jika pertanyaan di luar konteks STMK, jawab dengan santai dan tambahkan saran untuk kembali ke topik, misalnya: 'Wah, seru banget topiknya! Tapi aku lebih jago soal STMK, mau coba tanya jurusan?' "
                    "Jika informasi tidak tersedia di data_kampus.json, katakan 'Hmm, aku kurang yakin nih!' dan arahkan ke website resmi atau kontak resmi dengan nada ceria. "
                    "Gunakan bahasa Indonesia yang santai, jelas, dan profesional. Format teks rapi dengan daftar menggunakan tanda '-' dan hindari tanda bintang (*) atau spasi berlebih. "
                    "Untuk pertanyaan ambigu, minta klarifikasi dengan ramah, misalnya: 'Eh, aku bingung nih, maksudnya apa ya? Coba pakai kata kunci seperti jurusan atau fasilitas!' "
                    "Tambahkan sentuhan kreatif seperti emoji (😄, 😊) atau ajakan seperti 'Penasaran lagi? Ayo diskusi lebih lanjut!' dengan kata kunci: jurusan, fasilitas, visi, misi, akreditasi, whatsapp, kerja sama, atau fokus teknologi. Sarankan 'selesai diskusi' atau 'keluar dari ai' jika pengguna ingin berhenti."
                )
            },
            {"role": "user", "content": pesan}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()  # Raise an error for bad status codes
        reply = response.json()["choices"][0]["message"]["content"]
        # Rapikan teks setelah diterima dari AI
        reply = reply.replace("*", "").strip()  # Hapus tanda bintang
        reply = "\n".join(line.strip() for line in reply.split("\n") if line.strip())  # Bersihkan baris kosong dan spasi
        return reply
    except requests.RequestException:
        return "Ups, serverku lagi rewel nih! 😅 Coba lagi nanti atau cek https://trisaktimultimedia.ac.id ya!"

def clean_and_validate_response(ai_reply, user_msg):
    # Validasi situs resmi dan kontak WhatsApp
    if "website" in data_kampus and data_kampus["website"] not in ai_reply:
        ai_reply = ai_reply.replace("https://stmktriakti.ac.id", data_kampus["website"])
    if "contact" in data_kampus and "whatsapp" in data_kampus["contact"] and data_kampus["contact"]["whatsapp"] not in ai_reply:
        ai_reply = ai_reply.replace("+62 821-1859-9320", data_kampus["contact"]["whatsapp"])
    if "lokasi" in user_msg or "alamat" in user_msg:
        if data_kampus["address"] not in ai_reply:
            ai_reply = f"Alamat resmi STMK Trisakti: {data_kampus['address']}\n📍 Sumber: {data_kampus['website']}\nHmm, aku kurang yakin nih dengan info lain, coba tanyakan lagi ya!"
    # Rapikan teks
    ai_reply = ai_reply.replace("*", "").strip()  # Hapus tanda bintang
    ai_reply = "\n".join(line.strip() for line in ai_reply.split("\n") if line.strip())  # Bersihkan baris kosong dan spasi
    return ai_reply

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)