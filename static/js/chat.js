document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const chatBox = document.getElementById("chat-box");

  function appendMessage(sender, message) {
    const messageDiv = document.createElement("div");
    messageDiv.className = sender === "user" ? "chat-message user" : "chat-message ai";
    messageDiv.innerHTML = DOMPurify.sanitize(message);
    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", `<strong>Kamu:</strong> ${message}`);
    input.value = "";
    input.style.height = "auto";

    appendMessage("ai", "<em>TIMU sedang mengetik...</em>");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();
      const lastMsg = chatBox.querySelector(".chat-message.ai:last-child");
      if (data.reply) {
        lastMsg.innerHTML = DOMPurify.sanitize(`<strong>TIMU:</strong> ${data.reply}`);
      } else {
        lastMsg.innerHTML = "<em>Maaf, tidak ada balasan.</em>";
      }
    } catch (error) {
      const lastMsg = chatBox.querySelector(".chat-message.ai:last-child");
      lastMsg.innerHTML = "<em>Terjadi kesalahan. Silakan coba lagi nanti.</em>";
    }
  });

  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = (input.scrollHeight > 36 ? input.scrollHeight : 36) + "px";
  });
});

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute("data-theme");
  html.setAttribute("data-theme", current === "dark" ? "light" : "dark");
}