document.addEventListener("DOMContentLoaded", function () {
  const chatBox = document.querySelector(".chat-box");
  const chatForm = document.querySelector("#chat-form");
  const inputField = document.querySelector("#message-input");

  // Theme toggle
  const toggleButton = document.querySelector("#toggle-theme");
  toggleButton.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
  });

  // Load theme
  const savedTheme = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", savedTheme);

  // Auto-scroll
  function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  // Append message
  function appendMessage(sender, text, isHtml = false) {
    const message = document.createElement("div");
    message.className = "message " + sender;

    if (sender === "bot") {
      message.innerHTML = `
        <div class="avatar"></div>
        <div class="bubble">${isHtml ? text : escapeHTML(text)}</div>
      `;
    } else {
      message.innerHTML = `
        <div class="bubble">${escapeHTML(text)}</div>
      `;
    }

    chatBox.appendChild(message);
    scrollToBottom();
  }

  // Escape HTML to prevent injection
  function escapeHTML(str) {
    const div = document.createElement("div");
    div.innerText = str;
    return div.innerHTML;
  }

  // Show loading indicator
  function showLoading() {
    const loading = document.createElement("div");
    loading.className = "message bot loading";
    loading.innerHTML = `
      <div class="avatar"></div>
      <div class="bubble"><em>Sedang mengetik...</em></div>
    `;
    chatBox.appendChild(loading);
    scrollToBottom();
    return loading;
  }

  // Handle form submit
  chatForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const msg = inputField.value.trim();
    if (!msg) return;

    appendMessage("user", msg);
    inputField.value = "";

    const loading = showLoading();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: msg })
      });

      const data = await res.json();
      chatBox.removeChild(loading);

      if (data.reply) {
        appendMessage("bot", data.reply, true);
      } else if (data.error) {
        appendMessage("bot", "❌ " + data.error);
      } else {
        appendMessage("bot", "❌ Maaf, terjadi kesalahan.");
      }
    } catch (err) {
      console.error(err);
      chatBox.removeChild(loading);
      appendMessage("bot", "❌ Gagal terhubung ke server.");
    }
  });

  // Enter key to submit
  inputField.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });
});