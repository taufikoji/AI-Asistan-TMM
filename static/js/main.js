document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const typoBox = document.getElementById("typo-correction");

    // Cek apakah semua elemen ada
    if (!form || !input || !chatBox || !typoBox) {
        console.error("Error: Salah satu elemen HTML (chat-form, user-input, chat-box, typo-correction) tidak ditemukan!");
        return;
    }

    input.focus();

    // Inisialisasi chat dari backend
    function initializeChat(conversation) {
        if (conversation && Array.isArray(conversation)) {
            conversation.forEach(msg => {
                appendMessage(msg.content, msg.role === "user" ? "user" : "bot", true);
            });
        }
    }

    // Ambil data awal dari server
    fetch('/api/chat?init=true', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => res.json())
    .then(data => initializeChat(data.conversation))
    .catch(err => console.error("Gagal menginisialisasi chat:", err));

    function appendMessage(text, sender = "bot", isHTML = false) {
        const div = document.createElement("div");
        div.className = `message ${sender === "user" ? "user-message" : "ai-message"}`;
        div.innerHTML = isHTML ? text : escapeHTML(text);
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function escapeHTML(str) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        };
        return str.replace(/[&<>'"]/g, tag => map[tag] || tag);
    }

    function showLoading() {
        const div = document.createElement("div");
        div.className = "message ai-message";
        div.id = "loading-msg";
        div.textContent = "⏳ Sedang memproses...";
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function removeLoading() {
        const loadingMsg = document.getElementById("loading-msg");
        if (loadingMsg) loadingMsg.remove();
    }

    async function sendMessage(message) {
        appendMessage(message, "user");
        input.value = "";
        typoBox.style.display = "none";

        showLoading();

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
            });

            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

            const data = await res.json();
            removeLoading();

            if (data.corrected) {
                typoBox.textContent = `Koreksi ejaan: ${data.corrected}`;
                typoBox.style.display = "block";
            }

            if (data.reply) {
                typeReply(data.reply, data.language);
            } else if (data.error) {
                appendMessage(`Error: ${data.error}`, "bot");
            } else {
                appendMessage("Maaf, tidak ada balasan dari sistem.", "bot");
            }
        } catch (err) {
            removeLoading();
            appendMessage(`❌ Terjadi kesalahan: ${err.message}`, "bot");
            console.error("Error:", err);
        }
    }

    function typeReply(text, lang = "id") {
        const div = document.createElement("div");
        div.className = "message ai-message";
        chatBox.appendChild(div);

        let index = 0;
        const speed = lang === "id" ? 30 : 50; // Sesuaikan kecepatan berdasarkan bahasa
        const interval = setInterval(() => {
            div.innerHTML = `${escapeHTML(text.slice(0, index))}<span class='cursor'>▌</span>`;
            chatBox.scrollTop = chatBox.scrollHeight;
            index++;
            if (index > text.length) {
                clearInterval(interval);
                div.innerHTML = escapeHTML(text); // Gunakan escapeHTML untuk keamanan
            }
        }, speed);
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;
        sendMessage(message);
    });

    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });
});