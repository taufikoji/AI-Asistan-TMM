document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const chatContainer = document.getElementById("chat-container");

  // Fungsi render chat
  function renderMessage(role, message) {
    const msg = document.createElement("div");
    msg.className = `message ${role}`;
    msg.innerHTML = DOMPurify.sanitize(message);
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // Kirim pesan ke backend
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    renderMessage("user", `<span>${message}</span>`);
    userInput.value = "";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
      });

      const data = await response.json();

      if (data.error) {
        renderMessage("ai", `<span style="color: red;">❌ ${data.error}</span>`);
      } else {
        renderMessage("ai", data.reply);
      }
    } catch (error) {
      renderMessage("ai", `<span style="color: red;">❌ Gagal terhubung ke server</span>`);
    }
  });
});