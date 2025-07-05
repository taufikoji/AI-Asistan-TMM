document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".chat-form");
  const input = document.getElementById("user-input");
  const output = document.querySelector(".chat-output");
  const sendBtn = document.getElementById("send-btn");
  const themeToggle = document.getElementById("theme-toggle");

  // Load theme
  const currentTheme = localStorage.getItem("theme") || "light";
  document.documentElement.setAttribute("data-theme", currentTheme);

  // Theme toggle
  themeToggle.addEventListener("click", () => {
    const newTheme = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
  });

  // Scroll to bottom
  const scrollToBottom = () => {
    output.scrollTop = output.scrollHeight;
  };

  // Show message
  function appendMessage(content, sender = "bot") {
    const wrapper = document.createElement("div");
    wrapper.className = sender === "user" ? "user-message" : "bot-message";

    const avatar = document.createElement("div");
    avatar.className = "avatar";

    const bubble = document.createElement("div");
    bubble.className = "message";
    bubble.innerHTML = content;

    wrapper.appendChild(avatar);
    wrapper.appendChild(bubble);
    output.appendChild(wrapper);
    scrollToBottom();
  }

  // Submit form
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage(message, "user");
    input.value = "";
    sendBtn.disabled = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();

      if (data.error) {
        appendMessage("⚠️ " + data.error);
      } else {
        const response = data.reply || "Maaf, tidak ada jawaban.";
        appendMessage(response, "bot");
      }
    } catch (err) {
      appendMessage("⚠️ Terjadi kesalahan koneksi.");
    } finally {
      sendBtn.disabled = false;
    }
  });
});