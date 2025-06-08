import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
import json

load_dotenv()
app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

with open("data_kampus.json", "r", encoding="utf-8") as f:
    data_kampus = json.load(f)

def buat_prompt(user_question):
    info = "\n".join([f"- {key}: {val}" for key, val in data_kampus.items()])
    prompt = f"""
Kamu adalah asisten chatbot kampus STMK Trisakti. Jawablah dalam Bahasa Indonesia berdasarkan informasi berikut:

{info}

Pertanyaan: {user_question}
Jawaban:"""
    return prompt

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json["message"]
    prompt = buat_prompt(user_msg)

    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return jsonify({"reply": response.text.strip()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
