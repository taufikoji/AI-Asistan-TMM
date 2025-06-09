import os
from flask import Flask, render_template, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message")

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://stmk-trisakti-chatbot.com",  # ganti dengan domain kamu
            "X-Title": "STMK Chatbot"
        }

        data = {
            "model": "deepseek/deepseek-r1-0528:free",  # Model DeepSeek R1 yang gratis
            "messages": [
                {"role": "system", "content": "Kamu adalah asisten AI kampus STMK Trisakti. Jawab dalam bahasa Indonesia."},
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)