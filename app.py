import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

# Inisialisasi client
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

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",  # gunakan deepseek-coder jika untuk coding
            "messages": [
                {"role": "system", "content": "Kamu adalah asisten AI yang ramah dan membantu. Jawab dengan jelas dan dalam bahasa Indonesia."},
                {"role": "user", "content": user_msg}
            ]
        }

        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=data)

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            return jsonify({"reply": reply})
        else:
            return jsonify({"reply": "Terjadi kesalahan pada server DeepSeek."}), 500

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan internal: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)