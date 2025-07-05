document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const chatBox = document.getElementById("chat-box");

  // Auto-grow textarea
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = input.scrollHeight + "px";
  });

  // Scroll to bottom
  function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Tampilkan pesan di UI
  function appendMessage(sender, text, isLoading = false) {
    const messageEl = document.createElement("div");
    messageEl.className = `message ${sender}`;
    messageEl.innerHTML = isLoading ? "<em>⏳ Sedang mengetik...</em>" : DOMPurify.sanitize(text);
    chatBox.appendChild(messageEl);
    scrollToBottom();
    return messageEl;
  }

  // Kirim pesan ke API
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;

    appendMessage("user", msg);
    input.value = "";
    input.style.height = "auto";

    const loadingMsg = appendMessage("bot", "", true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg })
      });
      const data = await res.json();
      loadingMsg.innerHTML = DOMPurify.sanitize(data.reply || "⚠️ Maaf, tidak ada jawaban.");
    } catch (err) {
      loadingMsg.innerHTML = "❌ Terjadi kesalahan saat menghubungi AI.";
    }

    scrollToBottom();
  });
});