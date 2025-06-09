import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests

# Load variabel lingkungan
load_dotenv()

app = Flask(__name__)

# Ambil API key dari .env
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/widget")
def widget():
    return render_template("widget.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message")

        if not user_msg:
            return jsonify({"reply": "Pesan tidak boleh kosong."}), 400

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",  # bisa diganti ke "deepseek-coder" untuk coding
            "messages": [
                {
                    "role": "system",
                    "content": "Kamu adalah asisten AI kampus STMK Trisakti yang ramah. Jawab dalam bahasa Indonesia."
                },
                {
                    "role": "user",
                    "content": user_msg
                }
            ]
        }

        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=data)

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return jsonify({"reply": reply})
        else:
            # Log detail error ke console (bisa dilihat di Railway log)
            print("DeepSeek Error:", response.text)
            return jsonify({
                "reply": "Terjadi kesalahan pada server DeepSeek.",
                "status": response.status_code,
                "error": response.text
            }), 500

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan internal: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)