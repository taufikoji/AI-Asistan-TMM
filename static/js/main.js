// ================= Chatroom Functionality =================
document.addEventListener("DOMContentLoaded", () => {
  const chatForm = document.getElementById("chat-form");
  const userInput = document.getElementById("user-input");
  const chatBox = document.getElementById("chat-box");

  if (chatForm && userInput && chatBox) {
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const message = userInput.value.trim();
      if (!message) return;

      appendMessage("user", message);
      userInput.value = "";
      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });
        const data = await response.json();
        if (data.reply) {
          appendMessage("ai", data.reply);
        } else {
          appendMessage("ai", "⚠️ Tidak ada balasan dari server.");
        }
      } catch (err) {
        appendMessage("ai", "⚠️ Terjadi kesalahan koneksi.");
      }
    });

    function appendMessage(sender, text) {
      const div = document.createElement("div");
      div.classList.add("message", sender);
      div.innerHTML = text;
      chatBox.appendChild(div);
      chatBox.scrollTop = chatBox.scrollHeight;
    }
  }

  // ================== Brosur Download Button ==================
  const brosurBtn = document.getElementById("brosur-btn");
  if (brosurBtn) {
    brosurBtn.addEventListener("click", () => {
      window.open("/download-brosur", "_blank");
    });
  }

  // ================== Back to Home Button ==================
  const backHomeBtn = document.getElementById("back-to-home");
  if (backHomeBtn) {
    backHomeBtn.addEventListener("click", () => {
      window.location.href = "/";
    });
  }

  // ================== Toggle Password Show ==================
  const pwField = document.getElementById("password");
  const togglePw = document.getElementById("toggle-password");
  if (pwField && togglePw) {
    togglePw.addEventListener("click", () => {
      pwField.type = pwField.type === "password" ? "text" : "password";
    });
  }
});