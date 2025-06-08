import os
import json
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import openai

load_dotenv()
app = Flask(__name__)

# Load API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Load data kampus
with open("data_kampus.json", "r", encoding="utf-8") as f:
    data_kampus = json.load(f)

def buat_prompt(user_question):
    info = "\n".join([f"- {key}: {val}" for key, val in data_kampus.items()])
    prompt = f"""
Kamu adalah chatbot STMK Trisakti. Jawablah dalam Bahasa Indonesia berdasarkan informasi berikut:

{info}

Pertanyaan: {user_question}
Jawaban:
"""
    return prompt

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json["message"]
    prompt = buat_prompt(user_msg)

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Gunakan "gpt-4" jika kamu punya akses
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        reply = f"Terjadi kesalahan: {str(e)}"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))