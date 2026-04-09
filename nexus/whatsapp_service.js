/**
 * NEXUS WhatsApp Service (whatsapp-web.js)
 * ─────────────────────────────────────────
 * Emits JSON events to stdout (consumed by autoforze_bridge.py):
 *   { type: "qr",           qr: "<base64 PNG>" }
 *   { type: "authenticated" }
 *   { type: "ready",        phone: "<number>" }
 *   { type: "message",      from: "<number>", body: "<text>" }
 *   { type: "message_sent", to: "<number>", body: "<text>" }
 *   { type: "error",        message: "<msg>" }
 *   { type: "log",          message: "<msg>" }
 *
 * Run:  node whatsapp_service.js
 */

const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");
const QRCode = require("qrcode");
const http = require("http");

const SESSION_PATH = process.env.WA_SESSION_PATH || "/tmp/nexus_wa_session";
const NEXUS_API   = process.env.NEXUS_API_URL || "http://localhost:8000";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function emitLog(msg) {
  emit({ type: "log", message: msg });
}

/**
 * POST JSON to the FastAPI backend and return the parsed response body.
 */
function postToNexus(path, body) {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify(body);
    const url = new URL(path, NEXUS_API);
    const opts = {
      hostname: url.hostname,
      port:     url.port || 8000,
      path:     url.pathname,
      method:   "POST",
      headers: {
        "Content-Type":   "application/json",
        "Content-Length": Buffer.byteLength(data),
      },
    };
    const req = http.request(opts, (res) => {
      let raw = "";
      res.on("data", (d) => (raw += d));
      res.on("end", () => {
        try { resolve(JSON.parse(raw)); } catch { resolve({ reply: raw }); }
      });
    });
    req.on("error", reject);
    req.write(data);
    req.end();
  });
}

// ─── WhatsApp client ─────────────────────────────────────────────────────────

emitLog("[WA] Initializing WhatsApp engine…");

const SESSION_DATA_DIR = process.env.WA_CHROME_PROFILE || "/tmp/nexus_wa_chrome_profile";

emitLog(`[WA] Chrome profile dir: ${SESSION_DATA_DIR}`);

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: SESSION_PATH }),
  puppeteer: {
    headless: true,
    args: [
      `--user-data-dir=${SESSION_DATA_DIR}`,    // ← isolated profile, no conflict with system Chrome
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-extensions",
      "--disable-background-networking",
      "--disable-background-timer-throttling",
      "--disable-backgrounding-occluded-windows",
      "--disable-renderer-backgrounding",
      "--disable-accelerated-2d-canvas",
      "--no-first-run",
      "--no-zygote",
      "--disable-gpu",
      "--remote-debugging-port=0",              // ← random free port each time
    ],
  },
});


// ── QR ───────────────────────────────────────────────────────────────────────

client.on("qr", async (qr) => {
  try {
    const dataUrl = await QRCode.toDataURL(qr, {
      width: 300,
      margin: 2,
      color: { dark: "#000000", light: "#ffffff" },
    });
    emit({ type: "qr", qr: dataUrl });
    emitLog("[WA] QR generated — waiting for scan…");
  } catch (err) {
    emit({ type: "error", message: `QR generation failed: ${err.message}` });
  }
});

// ── Auth events ───────────────────────────────────────────────────────────────

client.on("authenticated", () => {
  emit({ type: "authenticated" });
  emitLog("[WA] Session authenticated ✓");
});

client.on("ready", () => {
  const info = client.info;
  const phone = info?.wid?.user || "unknown";
  emit({ type: "ready", phone });
  emitLog(`[WA] WhatsApp ready — connected as +${phone}`);
});

client.on("auth_failure", (msg) => {
  emit({ type: "error", message: `[WA] Authentication failed: ${msg}` });
  process.exit(1);
});

client.on("disconnected", (reason) => {
  emit({ type: "error", message: `[WA] Disconnected: ${reason}` });
  process.exit(0);
});

// ── Incoming messages → TaskForze command router ──────────────────────────────

client.on("message", async (msg) => {
  // Ignore own messages, group messages (for now), and status updates
  if (msg.fromMe) return;

  const body   = (msg.body || "").trim();
  const sender = msg.from; // e.g. "919XXXXXXXXX@c.us"
  const phone  = sender.split("@")[0]; // strip @c.us for logging

  emit({ type: "message", from: phone, body });
  emitLog(`[WA] Incoming from +${phone}: ${body.substring(0, 80)}`);

  try {
    // ── POST to the FastAPI command router ──────────────────────────────────
    const result = await postToNexus("/autoforze/wa/message", {
      from:  phone,
      body,
    });

    const reply = result.reply || result.summary || "✅ Done.";

    // Send reply back on WhatsApp
    await msg.reply(reply.substring(0, 4096));
    emit({ type: "message_sent", to: phone, body: reply.substring(0, 200) });
    emitLog(`[WA] Replied to +${phone}`);

  } catch (err) {
    emitLog(`[WA] Error handling message: ${err.message}`);
    // Best-effort fallback reply
    try {
      await msg.reply("⚠️ TaskForze is processing your request. Please wait.");
    } catch (_) {}
  }
});

// ─── Start ────────────────────────────────────────────────────────────────────

emitLog("[WA] Starting browser session…");
client.initialize().catch((err) => {
  emit({ type: "error", message: `[WA] Init failed: ${err.message}` });
  process.exit(1);
});
