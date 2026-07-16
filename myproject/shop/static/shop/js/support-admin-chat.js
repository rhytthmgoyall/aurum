let adminClient = null;
let adminChannel = null;
let adminConfig = null;
let currentChannelName = null;

const messages = document.getElementById("staffMessages");
const form = document.getElementById("staffChatForm");
const input = document.getElementById("staffChatInput");
const title = document.getElementById("chatTitle");

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function appendMessage(message, isStaff) {
  const item = document.createElement("div");
  item.className = `msg${isStaff ? " staff" : ""}`;

  const body = document.createElement("div");
  body.textContent = message.body;

  const meta = document.createElement("small");
  meta.textContent = `${message.sender || ""} - ${message.created_at || ""}`.trim();

  item.append(body, meta);
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
}

async function initAdminClient() {
  if (adminClient) return;

  const response = await fetch("/api/support/agora-token/");
  if (!response.ok) return;

  adminConfig = await response.json();

  adminClient = AgoraRTM.createInstance(adminConfig.app_id);
  await adminClient.login({
    uid: adminConfig.uid,
    token: adminConfig.token,
  });
}

async function joinConversation(channelName) {
  await initAdminClient();
  if (!adminClient) return;

  if (adminChannel) {
    await adminChannel.leave();
  }

  currentChannelName = channelName;
  adminChannel = adminClient.createChannel(channelName);
  await adminChannel.join();

  adminChannel.on("ChannelMessage", message => {
    const payload = JSON.parse(message.text);
    appendMessage(payload, payload.is_staff);
  });

  const historyResponse = await fetch(`/api/support/history/?channel=${encodeURIComponent(channelName)}`);
  if (!historyResponse.ok) return;

  const data = await historyResponse.json();

  messages.innerHTML = "";
  data.messages.forEach(message => appendMessage(message, message.is_staff));
}

document.querySelectorAll(".conversation").forEach(link => {
  link.addEventListener("click", async event => {
    event.preventDefault();
    const channelName = link.dataset.channel;
    title.textContent = link.dataset.title || link.textContent.trim();
    await joinConversation(channelName);
  });
});

form.addEventListener("submit", async event => {
  event.preventDefault();

  const body = input.value.trim();
  if (!body || !adminChannel || !currentChannelName) return;

  const savedResponse = await fetch("/api/support/message/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      body,
      channel: currentChannelName,
    }),
  });

  if (!savedResponse.ok) return;

  const saved = await savedResponse.json();

  const payload = {
    body: saved.body,
    sender: saved.sender,
    sender_id: adminConfig.uid,
    is_staff: true,
    created_at: saved.created_at,
  };

  await adminChannel.sendMessage({
    text: JSON.stringify(payload),
  });

  appendMessage(payload, true);
  input.value = "";
});
