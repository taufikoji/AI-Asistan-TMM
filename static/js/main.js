document.addEventListener("DOMContentLoaded", () => {
  const chatBox = document.getElementById("chat-box");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatStatus = document.getElementById("chat-status");

  // Fungsi menampilkan pesan ke UI
  function appendMessage(text, sender = "user") {
    const msg = document.createElement("div");
    msg.className = `chat-message ${sender}`;
    msg.innerHTML = text;
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Fungsi menampilkan loader
  function showTyping() {
    const typing = document.createElement("div");
    typing.className = "chat-message ai";
    typing.id = "typing-indicator";
    typing.innerHTML = `<span class="loader"></span> Sedang mengetik...`;
    chatBox.appendChild(typing);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function removeTyping() {
    const typing = document.getElementById("typing-indicator");
    if (typing) typing.remove();
  }

  // Event submit chat
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage(message, "user");
    chatInput.value = "";
    chatStatus.innerText = "Menunggu jawaban TIMU...";
    showTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();
      removeTyping();

      if (res.ok && data.reply) {
        appendMessage(data.reply, "ai");

        if (data.corrected && data.corrected !== message) {
          chatStatus.innerText = `✏️ Diperbaiki menjadi: "${data.corrected}"`;
        } else {
          chatStatus.innerText = "Silakan lanjut bertanya.";
        }
      } else {
        appendMessage("Maaf, terjadi kesalahan. Coba lagi nanti.", "ai");
        chatStatus.innerText = "Gagal memuat jawaban.";
      }
    } catch (err) {
      removeTyping();
      appendMessage("🚫 Gagal menghubungi server. Pastikan koneksi Anda aktif.", "ai");
      chatStatus.innerText = "Tidak dapat terhubung.";
      console.error(err);
    }
  });
});