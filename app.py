import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import openai

load_dotenv()

app = Flask(__name__)

# Konfigurasi API OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# Route untuk halaman utama
@app.route("/")
def index():
    return render_template("index.html")

# Route untuk chatbot
@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json["message"]

        # Kirim ke OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # pastikan model ini aktif di akunmu
            messages=[
                {"role": "system", "content": "Kamu adalah asisten chatbot kampus STMK Trisakti. Jawablah dalam Bahasa Indonesia."},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=1000,
            temperature=0.7,
        )

        reply = response["choices"][0]["message"]["content"].strip()
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan: {str(e)}"})

# Menyesuaikan untuk deploy di Railway
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Railway akan isi PORT otomatis
    app.run(debug=False, host="0.0.0.0", port=port)