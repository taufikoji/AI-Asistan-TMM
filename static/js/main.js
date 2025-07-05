document.addEventListener("DOMContentLoaded", () => {
  // === LANDING PAGE NAVIGATION ===
  const startChatBtn = document.getElementById("startChatBtn");
  const adminLoginBtn = document.getElementById("adminLoginBtn");

  if (startChatBtn) {
    startChatBtn.addEventListener("click", () => {
      window.location.href = "/chat";
    });
  }

  if (adminLoginBtn) {
    adminLoginBtn.addEventListener("click", () => {
      window.location.href = "/login";
    });
  }

  // === CHATBOT FUNCTIONALITY ===
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const chatBox = document.getElementById("chatBox");

  const appendMessage = (sender, text) => {
    const p = document.createElement("p");
    p.className = sender;
    p.innerHTML = text;
    chatBox.appendChild(p);
    chatBox.scrollTop = chatBox.scrollHeight;
  };

  const sendMessage = async () => {
    const message = chatInput.value.trim();
    if (!message) return;

    appendMessage("user", message);
    chatInput.value = "";
    appendMessage("bot", "<em>...</em>");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      const data = await res.json();
      chatBox.lastChild.remove(); // remove "... loading"

      if (data.error) {
        appendMessage("bot", `<span style="color:red;">${data.error}</span>`);
      } else {
        appendMessage("bot", data.reply);
      }
    } catch (err) {
      chatBox.lastChild.remove();
      appendMessage("bot", "<span style='color:red;'>Terjadi kesalahan koneksi.</span>");
    }
  };

  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage();
    });
  }

  // === ENTER KEY SHORTCUT ===
  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }
});