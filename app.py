import os
import json
import pickle
import faiss
import numpy as np
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import requests

load_dotenv()
app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Load FAISS dan teks
model = SentenceTransformer("all-MiniLM-L6-v2")
faiss_index = faiss.read_index("rag/faiss_index/index.bin")
with open("rag/faiss_index/texts.pkl", "rb") as f:
    texts = pickle.load(f)

# Fungsi untuk ambil top-k konteks
def get_context(query, top_k=5):
    query_embedding = model.encode([query])
    D, I = faiss_index.search(np.array(query_embedding), top_k)
    return "\n".join([texts[i] for i in I[0]])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    # Deteksi topik STMK/TMM
    stmk_keywords = [
        "stmk", "stmkt", "tmm", "trisakti multimedia",
        "sekolah tinggi media komunikasi trisakti",
        "trisakti school of multimedia"
    ]
    is_stmk_topic = any(keyword in user_message.lower() for keyword in stmk_keywords)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://example.com",
        "X-Title": "Chatbot-STMK-Trisakti"
    }

    system_prompt = "Jawablah dengan bahasa Indonesia yang profesional, sopan, dan mudah dipahami. Jangan gunakan markdown seperti ** atau #."

    # Prompt berbasis context RAG
    if is_stmk_topic:
        context = get_context(user_message)
        prompt = f"""
Berikut adalah informasi yang relevan dari situs resmi trisaktimultimedia.ac.id:
{context}

Berdasarkan informasi tersebut, jawab pertanyaan berikut secara ringkas, akurat, dan profesional:
{user_message}
        """
    else:
        prompt = user_message

    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code == 200:
            reply = response.json()["choices"][0]["message"]["content"]
            clean_reply = reply.replace("**", "").replace("#", "").strip()
            return jsonify({"reply": clean_reply})
        else:
            return jsonify({
                "error": "API Error",
                "details": response.text
            }), response.status_code

    except Exception as e:
        return jsonify({"error": "Exception", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)