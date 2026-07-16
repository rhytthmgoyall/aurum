let supportClient = null;
let supportChannel = null;
let supportConfig = null;

const supportToggle = document.getElementById("supportChatToggle");
const supportPanel = document.getElementById("supportChatPanel");
const supportClose = document.getElementById("supportChatClose");
const supportMessages = document.getElementById("supportChatMessages");
const supportForm = document.getElementById("supportChatForm");
const supportInput = document.getElementById("supportChatInput");

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function renderSupportIntro() {
  supportMessages.innerHTML = `
    <div class="support-chat-intro">
      <div>
        <strong>Welcome to AURUM</strong>
        <p>Ask us about sizing, materials, shipping, or finding the right piece.</p>
      </div>
    </div>
  `;
}

function appendSupportMessage(message, isMine) {
  const item = document.createElement("div");
  item.className = `support-chat-message${isMine ? " mine" : ""}`;

  const body = document.createElement("div");
  body.className = "support-chat-message-body";
  body.textContent = message.body;

  const meta = document.createElement("small");
  meta.textContent = `${message.created_at || ""}`.trim();

  item.append(body, meta);
  supportMessages.appendChild(item);
  supportMessages.scrollTop = supportMessages.scrollHeight;
}

async function loadSupportHistory() {
  const response = await fetch("/api/support/history/");
  if (!response.ok) return;

  const data = await response.json();
  supportMessages.innerHTML = "";

  if (data.messages.length) {
    data.messages.forEach(message => {
      appendSupportMessage(message, !message.is_staff);
    });
  } else {
    renderSupportIntro();
  }
}

async function connectSupportChannel(config) {
  supportConfig = config;

  supportClient = AgoraRTM.createInstance(supportConfig.app_id);
  await supportClient.login({
    uid: supportConfig.uid,
    token: supportConfig.token,
  });

  supportChannel = supportClient.createChannel(supportConfig.channel_name);
  await supportChannel.join();

  supportChannel.on("ChannelMessage", message => {
    const payload = JSON.parse(message.text);
    appendSupportMessage(payload, payload.sender_id === supportConfig.uid);
  });

  await loadSupportHistory();
  return true;
}

async function initGuestSupportChat() {
  const response = await fetch("/api/support/guest-start/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) return false;

  const config = await response.json();
  return await connectSupportChannel(config);
}

async function initSupportChat() {
  if (supportClient) return true;

  try {
    const response = await fetch("/api/support/agora-token/");
    if (response.status === 401) {
      return await initGuestSupportChat();
    }

    if (!response.ok) return false;

    const config = await response.json();
    return await connectSupportChannel(config);
  } catch (error) {
    console.warn("Support chat initialization failed:", error);
    return false;
  }
}

supportToggle.addEventListener("click", async () => {
  supportPanel.classList.add("is-open");

  try {
    await initSupportChat();
  } catch (error) {
    console.warn("Support chat start failed:", error);
  }

  supportForm.classList.remove("is-hidden");
});

supportClose.addEventListener("click", () => {
  supportPanel.classList.remove("is-open");
});

supportForm.addEventListener("submit", async event => {
  event.preventDefault();

  const body = supportInput.value.trim();
  if (!body) return;

  const savedResponse = await fetch("/api/support/message/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ body }),
  });

  if (!savedResponse.ok) return;

  const saved = await savedResponse.json();

  const payload = {
    body: saved.body,
    sender: saved.sender,
    sender_id: supportConfig.uid,
    is_staff: false,
    created_at: saved.created_at,
  };

  if (supportChannel) {
    try {
      await supportChannel.sendMessage({
        text: JSON.stringify(payload),
      });
    } catch (error) {
      console.warn("Failed to send support message over RTM:", error);
    }
  }

  appendSupportMessage(payload, true);
  supportInput.value = "";

  const aiResponse = await fetch("/api/support/ai-reply/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({ body }),
  });

  if (!aiResponse.ok) return;

  const aiMessage = await aiResponse.json();

  if (supportChannel) {
    try {
      await supportChannel.sendMessage({
        text: JSON.stringify(aiMessage),
      });
    } catch (error) {
      console.warn("Failed to send AI reply over RTM:", error);
    }
  }

  appendSupportMessage(aiMessage, false);
});
