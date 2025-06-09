from flask import Flask, render_template, request
import openai
import os
from dotenv import load_dotenv

load_dotenv()  # Memuat file .env

# Inisialisasi client OpenAI
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form["message"]

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Kamu adalah chatbot STMK Trisakti. Jawablah dengan jelas dan ringkas dalam Bahasa Indonesia."},
                {"role": "user", "content": user_message}
            ]
        )
        bot_reply = response.choices[0].message.content
    except Exception as e:
        bot_reply = f"Terjadi kesalahan: {e}"

    return render_template("index.html", user_message=user_message, bot_reply=bot_reply)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Railway akan isi PORT
    app.run(debug=False, host="0.0.0.0", port=port)