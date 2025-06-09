import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

# Inisialisasi client DeepSeek
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

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

        # Siapkan pesan
        messages = [
            {"role": "system", "content": "Kamu adalah asisten AI yang ramah dan membantu. Jawab dalam bahasa Indonesia."},
            {"role": "user", "content": user_msg}
        ]

        # Kirim ke DeepSeek Reasoner
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=messages
        )

        # Ambil hasil
        reply = response.choices[0].message.content
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": f"Terjadi kesalahan internal: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)