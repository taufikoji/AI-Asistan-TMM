document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("user-input");
  const sendBtn = document.getElementById("send-btn");
  const chatBox = document.getElementById("chat-box");

  const scrollToBottom = () => {
    chatBox.scrollTop = chatBox.scrollHeight;
  };

  const addMessage = (text, type = "user") => {
    const msg = document.createElement("div");
    msg.className = type === "user" ? "user-message" : "ai-message";
    msg.innerHTML = DOMPurify.sanitize(text);
    chatBox.appendChild(msg);
    scrollToBottom();
  };

  const sendMessage = async () => {
    const message = input.value.trim();
    if (!message) return;

    addMessage(message, "user");
    input.value = "";
    sendBtn.disabled = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();

      if (res.ok && data.reply) {
        addMessage(data.reply, "ai");
      } else {
        addMessage("⚠️ Maaf, terjadi kesalahan pada sistem. Coba beberapa saat lagi.", "ai");
      }
    } catch (err) {
      addMessage("⚠️ Koneksi gagal. Periksa jaringan internet Anda.", "ai");
    } finally {
      sendBtn.disabled = false;
    }
  };

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
});