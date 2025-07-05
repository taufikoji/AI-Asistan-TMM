document.addEventListener("DOMContentLoaded", () => {
  const modeToggle = document.getElementById("mode-toggle");
  const theme = localStorage.getItem("theme") || "dark";
  document.documentElement.setAttribute("data-theme", theme);

  if (modeToggle) {
    modeToggle.textContent = theme === "dark" ? "🌞" : "🌙";
    modeToggle.addEventListener("click", () => {
      const currentTheme = document.documentElement.getAttribute("data-theme");
      const newTheme = currentTheme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", newTheme);
      localStorage.setItem("theme", newTheme);
      modeToggle.textContent = newTheme === "dark" ? "🌞" : "🌙";
    });
  }

  // Chatroom functionality
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const chatBox = document.getElementById("chat-box");

  if (chatForm && chatInput && chatBox) {
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const userInput = chatInput.value.trim();
      if (!userInput) return;

      appendMessage("user", userInput);
      chatInput.value = "";
      chatBox.scrollTop = chatBox.scrollHeight;

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userInput }),
        });

        const data = await response.json();
        if (data.reply) {
          appendMessage("bot", data.reply);
        } else if (data.error) {
          appendMessage("bot", `❌ ${data.error}`);
        }
      } catch (err) {
        appendMessage("bot", "❌ Gagal terhubung ke server.");
      }

      chatBox.scrollTop = chatBox.scrollHeight;
    });
  }

  function appendMessage(sender, message) {
    const bubble = document.createElement("div");
    bubble.classList.add("bubble", sender);
    bubble.innerHTML = message;
    chatBox.appendChild(bubble);
  }
});
