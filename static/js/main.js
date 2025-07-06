document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatBox = document.getElementById("chat-box");
  const loadingBubble = document.createElement("div");
  loadingBubble.className = "message ai typing";
  loadingBubble.innerHTML = "<p>✍️ TIMU sedang mengetik...</p>";

  function addMessage(content, type = "user") {
    const message = document.createElement("div");
    message.className = `message ${type}`;
    message.innerHTML = `<div class="bubble">${content}</div>`;
    chatBox.appendChild(message);
    scrollToBottom();
  }

  function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function showTyping(show) {
    if (show) {
      chatBox.appendChild(loadingBubble);
    } else if (chatBox.contains(loadingBubble)) {
      chatBox.removeChild(loadingBubble);
    }
    scrollToBottom();
  }

  async function sendMessage(message) {
    addMessage(message, "user");
    showTyping(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await res.json();

      if (data.reply) {
        showTyping(false);
        setTimeout(() => {
          addMessage(data.reply, "ai");
        }, 300);
      } else {
        showTyping(false);
        addMessage("<p>⚠️ Jawaban tidak tersedia. Coba lagi nanti.</p>", "ai");
      }
    } catch (err) {
      console.error(err);
      showTyping(false);
      addMessage("<p>❌ Gagal terhubung ke server. Coba periksa koneksi Anda.</p>", "ai");
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (message !== "") {
      sendMessage(message);
      chatInput.value = "";
    }
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Auto-focus saat halaman dibuka
  chatInput.focus();
});