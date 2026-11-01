(function () {
  "use strict";

  var scriptTag = document.currentScript || (function () {
    var scripts = document.getElementsByTagName("script");
    return scripts[scripts.length - 1];
  })();

  var widgetId = scriptTag.getAttribute("data-widget-id");
  var apiBase = scriptTag.getAttribute("data-api-base");
  var primaryColor = scriptTag.getAttribute("data-color") || "#4f46e5";

  if (!widgetId || !apiBase) {
    console.error("[ai-sales-widget] data-widget-id and data-api-base are required.");
    return;
  }

  apiBase = apiBase.replace(/\/$/, "");
  var SESSION_KEY = "ai_sales_widget_session_" + widgetId;
  var CONVERSATION_KEY = "ai_sales_widget_conversation_" + widgetId;

  function getSessionId() {
    var id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  function getConversationId() {
    return sessionStorage.getItem(CONVERSATION_KEY);
  }

  function setConversationId(id) {
    sessionStorage.setItem(CONVERSATION_KEY, id);
  }

  var style = document.createElement("style");
  style.textContent =
    ".aisw-bubble{position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;" +
    "background:" + primaryColor + ";box-shadow:0 4px 12px rgba(0,0,0,.2);cursor:pointer;z-index:999999;" +
    "display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;border:none;}" +
    ".aisw-window{position:fixed;bottom:88px;right:20px;width:340px;max-width:90vw;height:460px;max-height:70vh;" +
    "background:#fff;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.25);display:none;flex-direction:column;" +
    "overflow:hidden;z-index:999999;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}" +
    ".aisw-window.aisw-open{display:flex;}" +
    ".aisw-header{background:" + primaryColor + ";color:#fff;padding:14px 16px;font-size:14px;font-weight:600;}" +
    ".aisw-messages{flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;background:#f7f7fa;}" +
    ".aisw-msg{max-width:80%;padding:8px 12px;border-radius:10px;font-size:13px;line-height:1.4;}" +
    ".aisw-msg-customer{align-self:flex-end;background:" + primaryColor + ";color:#fff;}" +
    ".aisw-msg-ai{align-self:flex-start;background:#fff;color:#222;border:1px solid #e5e5ea;}" +
    ".aisw-input-row{display:flex;border-top:1px solid #e5e5ea;padding:8px;gap:6px;}" +
    ".aisw-input-row input{flex:1;border:1px solid #e5e5ea;border-radius:8px;padding:8px 10px;font-size:13px;outline:none;}" +
    ".aisw-input-row button{background:" + primaryColor + ";color:#fff;border:none;border-radius:8px;padding:8px 12px;" +
    "font-size:13px;cursor:pointer;}" +
    ".aisw-input-row button:disabled{opacity:.5;cursor:default;}" +
    ".aisw-rating{display:flex;gap:6px;margin-top:4px;}" +
    ".aisw-rating button{background:none;border:none;cursor:pointer;font-size:13px;opacity:.5;padding:2px;}" +
    ".aisw-rating button:hover{opacity:1;}" +
    ".aisw-rating button.aisw-rated{opacity:1;}";
  document.head.appendChild(style);

  var bubble = document.createElement("button");
  bubble.className = "aisw-bubble";
  bubble.setAttribute("aria-label", "Open chat");
  bubble.textContent = "💬";

  var win = document.createElement("div");
  win.className = "aisw-window";

  var header = document.createElement("div");
  header.className = "aisw-header";
  header.textContent = "Chat with us";

  var messages = document.createElement("div");
  messages.className = "aisw-messages";

  var inputRow = document.createElement("div");
  inputRow.className = "aisw-input-row";
  var input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Type a message...";
  var sendBtn = document.createElement("button");
  sendBtn.textContent = "Send";
  inputRow.appendChild(input);
  inputRow.appendChild(sendBtn);

  win.appendChild(header);
  win.appendChild(messages);
  win.appendChild(inputRow);

  document.body.appendChild(bubble);
  document.body.appendChild(win);

  var configLoaded = false;

  function loadConfig() {
    if (configLoaded) return;
    configLoaded = true;
    fetch(apiBase + "/widget/" + widgetId + "/config/")
      .then(function (res) {
        if (!res.ok) throw new Error("config failed");
        return res.json();
      })
      .then(function (config) {
        header.textContent = config.agent_name || "Chat with us";
        if (config.greeting && messages.children.length === 0) {
          appendMessage("ai", config.greeting);
        }
      })
      .catch(function () {
        /* widget still usable without config; greeting/name just stay default */
      });
  }

  function appendMessage(sender, content, messageId) {
    var el = document.createElement("div");
    el.className = "aisw-msg " + (sender === "customer" ? "aisw-msg-customer" : "aisw-msg-ai");
    el.textContent = content;
    messages.appendChild(el);

    if (sender === "ai" && messageId) {
      messages.appendChild(buildRatingRow(messageId));
    }

    messages.scrollTop = messages.scrollHeight;
  }

  function buildRatingRow(messageId) {
    var row = document.createElement("div");
    row.className = "aisw-rating";

    var up = document.createElement("button");
    up.textContent = "👍";
    up.setAttribute("aria-label", "This reply was helpful");

    var down = document.createElement("button");
    down.textContent = "👎";
    down.setAttribute("aria-label", "This reply was not helpful");

    function rate(value) {
      up.disabled = true;
      down.disabled = true;
      (value === "up" ? up : down).classList.add("aisw-rated");
      fetch(apiBase + "/widget/" + widgetId + "/messages/" + messageId + "/rate/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating: value }),
      }).catch(function () {
        /* rating is a nice-to-have — a failed request doesn't need surfacing to the customer */
      });
    }

    up.addEventListener("click", function () { rate("up"); });
    down.addEventListener("click", function () { rate("down"); });

    row.appendChild(up);
    row.appendChild(down);
    return row;
  }

  function sendMessage() {
    var text = input.value.trim();
    if (!text) return;

    appendMessage("customer", text);
    input.value = "";
    input.disabled = true;
    sendBtn.disabled = true;

    fetch(apiBase + "/widget/" + widgetId + "/chat/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        session_id: getSessionId(),
        conversation_id: getConversationId() || undefined,
      }),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("chat failed");
        return res.json();
      })
      .then(function (data) {
        setConversationId(data.conversation_id);
        appendMessage("ai", data.message.content, data.message.id);
      })
      .catch(function () {
        appendMessage("ai", "Sorry, something went wrong. Please try again.");
      })
      .finally(function () {
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
      });
  }

  bubble.addEventListener("click", function () {
    win.classList.toggle("aisw-open");
    if (win.classList.contains("aisw-open")) {
      loadConfig();
      input.focus();
    }
  });

  sendBtn.addEventListener("click", sendMessage);
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter") sendMessage();
  });
})();
