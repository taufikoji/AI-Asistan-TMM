from flask import Flask, render_template, request, jsonify
import json, os, re
import google.generativeai as genai
from datetime import datetime

# Konfigurasi Gemini API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("⚠️ Environment variable 'GEMINI_API_KEY' tidak ditemukan.")
genai.configure(api_key=api_key)

app = Flask(__name__)

# Load data universitas
with open("trisakti_info.json", "r", encoding="utf-8") as f:
    trisakti_data = json.load(f)

# Riwayat percakapan
chat_history = []

def simpan_riwayat(role, message):
    chat_history.append({"role": role, "message": message})
    if len(chat_history) > 50:
        chat_history.pop(0)
    with open("chat_history.json", "w", encoding="utf-8") as file:
        json.dump(chat_history, file, ensure_ascii=False, indent=2)

@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/chat")
def chat():
    return render_template("chatroom.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    user_message = request.json.get("message", "").strip()
    if not user_message:
        return jsonify({"response": "Pesan tidak boleh kosong."})

    simpan_riwayat("user", user_message)

    # Coba cocokkan alias jurusan
    jurusan_alias = {}
    for p in trisakti_data["academic_programs"]:
        for alias in p.get("aliases", []):
            jurusan_alias[alias.lower()] = p["name"]

    for alias, full_name in jurusan_alias.items():
        if alias in user_message.lower():
            jurusan_info = next(
                (p for p in trisakti_data["academic_programs"] if p["name"] == full_name), None
            )
            if jurusan_info:
                response = (
                    f"Berikut info tentang **{jurusan_info['name']}**:\n\n"
                    f"{jurusan_info['description']}\n\n"
                    f"Durasi: {jurusan_info['duration']}\n"
                    f"Gelar: {jurusan_info['degree']}\n"
                    f"Fakultas: {jurusan_info['faculty']}\n"
                    f"Akreditasi: {jurusan_info['accreditation']}\n\n"
                    f"Sumber: {trisakti_data['institution']['website']}"
                )
                simpan_riwayat("assistant", response)
                return jsonify({"response": response})

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            f"Kamu adalah asisten kampus bernama TIMU dari Universitas Trisakti. "
            f"Jawab dengan sopan dan natural: {user_message}"
        )
        hasil = response.text.strip()
    except Exception as e:
        hasil = f"⚠️ Terjadi kesalahan: {str(e)}"

    simpan_riwayat("assistant", hasil)
    return jsonify({"response": hasil})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
