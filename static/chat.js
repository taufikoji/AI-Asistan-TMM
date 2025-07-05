document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");
  const sendButton = document.getElementById("send-button");
  const themeToggle = document.getElementById("theme-toggle");

  // Load theme from localStorage
  if (localStorage.getItem("theme") === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  }

  themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    addUserMessage(message);
    input.value = "";
    input.disabled = true;
    sendButton.disabled = true;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();
      if (data.reply) {
        addAIMessage(data.reply);
      } else {
        addAIMessage("⚠️ Maaf, respons kosong atau terjadi kesalahan.");
      }
    } catch (err) {
      addAIMessage("⚠️ Gagal menghubungi server.");
    }

    input.disabled = false;
    sendButton.disabled = false;
    input.focus();
  });

  function addUserMessage(text) {
    const wrapper = document.createElement("div");
    wrapper.className = "user-message";
    const bubble = document.createElement("div");
    bubble.className = "message";
    bubble.textContent = text;
    wrapper.appendChild(bubble);
    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function addAIMessage(html) {
    const wrapper = document.createElement("div");
    wrapper.className = "ai-message";

    const avatar = document.createElement("div");
    avatar.className = "avatar-glow";
    wrapper.appendChild(avatar);

    const bubble = document.createElement("div");
    bubble.className = "message";
    bubble.innerHTML = DOMPurify.sanitize(html);
    wrapper.appendChild(bubble);

    chatBox.appendChild(wrapper);
    chatBox.scrollTop = chatBox.scrollHeight;
  }
});