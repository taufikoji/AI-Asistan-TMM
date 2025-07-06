document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatBox = document.getElementById("chat-box");
  const statusDiv = document.getElementById("chat-status");

  function appendMessage(sender, message, isHTML = false) {
    const div = document.createElement("div");
    div.className = sender === "user" ? "chat-message user" : "chat-message ai";
    div.innerHTML = isHTML ? message : escapeHTML(message);
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function setStatus(message, loading = false) {
    statusDiv.innerHTML = loading
      ? `<span class="loader"></span> ${message}`
      : message;
  }

  function escapeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    chatInput.value = "";
    setStatus("Menunggu jawaban dari TIMU...", true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await response.json();

      if (data.reply) {
        appendMessage("ai", data.reply, true);
      } else if (data.error) {
        appendMessage("ai", `⚠️ ${data.error}`);
      } else {
        appendMessage("ai", "⚠️ Tidak ada jawaban dari AI.");
      }

      if (data.corrected && data.corrected !== message) {
        setStatus(`Koreksi ejaan: <em>${data.corrected}</em>`, false);
      } else {
        setStatus("Selesai", false);
      }
    } catch (error) {
      appendMessage("ai", "⚠️ Gagal terhubung ke server.");
      setStatus("Terjadi kesalahan.", false);
    }
  });
});