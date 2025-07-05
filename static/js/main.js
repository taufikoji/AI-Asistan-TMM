document.addEventListener("DOMContentLoaded", function () {
  // === THEME TOGGLE ===
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const html = document.documentElement;
      const currentTheme = html.getAttribute("data-theme");
      const newTheme = currentTheme === "dark" ? "light" : "dark";
      html.setAttribute("data-theme", newTheme);
      localStorage.setItem("theme", newTheme);
    });

    // Set theme on load
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
      document.documentElement.setAttribute("data-theme", savedTheme);
    }
  }

  // === CHATROOM ===
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatBox = document.getElementById("chatBox");

  if (chatForm && chatInput && chatBox) {
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const userMsg = chatInput.value.trim();
      if (!userMsg) return;

      appendBubble("user", userMsg);
      chatInput.value = "";
      chatInput.disabled = true;

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: userMsg }),
        });
        const data = await res.json();

        if (data.reply) {
          appendBubble("ai", data.reply);
        } else {
          appendBubble("ai", "⚠️ Maaf, saya tidak dapat menjawab saat ini.");
        }
      } catch (err) {
        appendBubble("ai", "❌ Koneksi gagal.");
      } finally {
        chatInput.disabled = false;
        chatInput.focus();
      }
    });

    function appendBubble(role, message) {
      const bubble = document.createElement("div");
      bubble.className = `bubble ${role}`;
      bubble.innerHTML = message;
      chatBox.appendChild(bubble);
      chatBox.scrollTop = chatBox.scrollHeight;
    }
  }

  // === LOGIN PAGE: ENTER TO SUBMIT ===
  const loginInput = document.querySelector("input[name='password']");
  if (loginInput) {
    loginInput.addEventListener("keyup", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        loginInput.form.submit();
      }
    });
  }

  // === ANIMATED LOGO ===
  const logo = document.querySelector(".logo-glow");
  if (logo) {
    logo.addEventListener("mouseenter", () => {
      logo.style.transform = "scale(1.05)";
    });
    logo.addEventListener("mouseleave", () => {
      logo.style.transform = "scale(1)";
    });
  }
});