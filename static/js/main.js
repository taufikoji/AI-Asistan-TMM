// ======================= Mode Dark/Light =======================
document.addEventListener("DOMContentLoaded", () => {
  const themeToggle = document.getElementById("theme-toggle");
  const html = document.documentElement;

  // Toggle theme
  themeToggle?.addEventListener("click", () => {
    const current = html.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });

  // Load saved theme
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    html.setAttribute("data-theme", savedTheme);
  }
});

// ======================= Chat Function =======================
async function sendMessage() {
  const input = document.getElementById("message-input");
  const text = input.value.trim();
  if (!text) return;

  appendMessage("user", text);
  input.value = "";

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();

    if (data.reply) {
      appendMessage("ai", data.reply);
    } else {
      appendMessage("ai", "⚠️ Maaf, tidak ada jawaban. Silakan coba lagi.");
    }
  } catch (error) {
    appendMessage("ai", "⚠️ Gagal menghubungi server.");
  }
}

function appendMessage(sender, text) {
  const box = document.getElementById("chat-box");
  const msg = document.createElement("div");
  msg.className = `msg ${sender}`;
  msg.innerHTML = `<p>${text}</p>`;
  box.appendChild(msg);
  box.scrollTop = box.scrollHeight;
}

// ======================= Enter to Send =======================
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("message-input");
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  const sendBtn = document.getElementById("send-button");
  sendBtn?.addEventListener("click", sendMessage);
});