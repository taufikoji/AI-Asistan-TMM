const chatBox = document.getElementById('chat-box');
const input = document.getElementById('message');

function appendMessage(sender, message) {
  const msgDiv = document.createElement('div');
  msgDiv.className = sender;
  msgDiv.innerHTML = `<strong>${sender === 'user' ? 'Anda' : 'TIMU'}:</strong> ${message}`;
  chatBox.appendChild(msgDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  appendMessage('user', text);
  input.value = '';
  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: text })
  })
  .then(res => res.json())
  .then(data => {
    if (data.reply) appendMessage('ai', data.reply);
    else appendMessage('ai', '❌ Maaf, terjadi kesalahan.');
  })
  .catch(() => appendMessage('ai', '⚠️ Gagal terhubung ke server.'));
}