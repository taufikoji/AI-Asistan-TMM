document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("chat-form");
    const input = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const typoBox = document.getElementById("typo-correction");
    const debugStatus = document.getElementById("debug-status");

    if (!form || !input || !chatBox || !typoBox || !debugStatus) {
        console.error("Error: Salah satu elemen HTML tidak ditemukan!");
        console.log("Elemen yang ada:", { form, input, chatBox, typoBox, debugStatus });
        if (debugStatus) debugStatus.textContent = "Error: Elemen hilang!";
        return;
    }

    debugStatus.textContent = "Siap!";
    input.focus();

    function initializeChat(conversation) {
        if (conversation && Array.isArray(conversation)) {
            conversation.forEach(msg => {
                appendMessage(msg.content, msg.role === "user" ? "user" : "bot", true);
            });
        } else {
            console.warn("Inisialisasi chat: conversation tidak valid", conversation);
            debugStatus.textContent = "Inisialisasi gagal!";
        }
    }

    fetch('/api/chat?init=true', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(res => {
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return res.json();
    })
    .then(data => {
        initializeChat(data.conversation);
        debugStatus.textContent = "Inisialisasi selesai.";
    })
    .catch(err => {
        console.error("Gagal menginisialisasi chat:", err);
        debugStatus.textContent = `Inisialisasi gagal: ${err.message}`;
    });

    function appendMessage(text, sender = "bot", isHTML = false) {
        console.log(`Menambahkan pesan: ${text} dari ${sender}`);
        const div = document.createElement("div");
        div.className = `message ${sender === "user" ? "user-message" : "ai-message"}`;
        div.innerHTML = isHTML ? text : escapeHTML(text);
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
        chatBox.removeChild(chatBox.querySelector(".placeholder-text")); // Hapus placeholder
        return div;
    }

    function escapeHTML(str) {
        const map = {
            '&': '&',
            '<': '<',
            '>': '>',
            "'": ''',
            '"': '"'
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
        console.log("Mengirim pesan:", message);
        debugStatus.textContent = "Mengirim pesan...";
        const userMessageDiv = appendMessage(message, "user");
        if (!userMessageDiv) {
            console.error("Gagal menambahkan pesan pengguna");
            debugStatus.textContent = "Gagal menambahkan pesan!";
            return;
        }
        input.value = "";
        typoBox.style.display = "none";

        showLoading();

        try {
            const res = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message }),
            });

            console.log("Respons status:", res.status);
            debugStatus.textContent = `Status: ${res.status}`;
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

            const data = await res.json();
            console.log("Respons data:", data);
            debugStatus.textContent = "Menerima respons...";
            removeLoading();

            if (data.corrected) {
                typoBox.textContent = `Koreksi ejaan: ${data.corrected}`;
                typoBox.style.display = "block";
            }

            if (data.reply) {
                typeReply(data.reply, data.language);
                debugStatus.textContent = "Respon ditampilkan.";
            } else if (data.error) {
                appendMessage(`Error: ${data.error}`, "bot");
                debugStatus.textContent = `Error: ${data.error}`;
            } else {
                appendMessage("Maaf, tidak ada balasan dari sistem. Cek log untuk detail.", "bot");
                debugStatus.textContent = "Tidak ada balasan.";
            }
        } catch (err) {
            removeLoading();
            appendMessage(`❌ Terjadi kesalahan: ${err.message}`, "bot");
            console.error("Error:", err);
            debugStatus.textContent = `Error: ${err.message}`;
        }
    }

    function typeReply(text, lang = "id") {
        const div = appendMessage("", "bot");
        if (!div) {
            console.error("Gagal membuat div untuk typeReply");
            appendMessage("Gagal menampilkan respons, coba lagi.", "bot");
            debugStatus.textContent = "Gagal menampilkan respons!";
            return;
        }

        let index = 0;
        const speed = lang === "id" ? 30 : 50;
        const interval = setInterval(() => {
            div.innerHTML = `${escapeHTML(text.slice(0, index))}<span class='cursor'>▌</span>`;
            chatBox.scrollTop = chatBox.scrollHeight;
            index++;
            if (index > text.length) {
                clearInterval(interval);
                div.innerHTML = escapeHTML(text);
                div.style.transform = "scale(1.05)";
                setTimeout(() => div.style.transform = "scale(1)", 200);
                debugStatus.textContent = "Respon selesai.";
            }
        }, speed);
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) {
            console.log("Pesan kosong, pengiriman dibatalkan.");
            debugStatus.textContent = "Pesan kosong!";
            return;
        }
        sendMessage(message);
    });

    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            form.requestSubmit();
        }
    });
});