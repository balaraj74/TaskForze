"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Terminal, Sparkles, Smartphone, CheckCircle2, X, Loader2,
  Wifi, SendHorizonal, Bot, User, Zap, GitBranch, Clock,
  RefreshCw, ChevronRight, Rocket, Info,
} from "lucide-react";

const API = "http://localhost:8000";

// ────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────
type WaStep = "idle" | "starting" | "qr" | "authenticated" | "ready" | "error";
type Stage  = "idle" | "understand" | "clarify" | "confirm" | "build" | "done" | "error";

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  ts: Date;
  stage?: Stage;
}

interface Slots {
  trigger?:    string;
  action?:     string;
  channel?:    string;
  condition?:  string;
  frequency?:  string;
  confidence?: number;
}

interface AutomationStep { id: string; type: string; label: string; config?: Record<string, unknown> }
interface Automation {
  id:          string;
  name:        string;
  description: string;
  steps:       AutomationStep[];
  channel:     string;
  status:      string;
}

// ────────────────────────────────────────────────────────────────────────────
// WhatsApp QR Modal (unchanged look, cleaned up)
// ────────────────────────────────────────────────────────────────────────────
function WhatsAppModal({
  onAuthenticated, onClose,
}: { onAuthenticated: (phone: string) => void; onClose: () => void }) {
  const [step, setStep]       = useState<WaStep>("starting");
  const [qrDataUrl, setQr]    = useState<string | null>(null);
  const [phone, setPhone]     = useState<string | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const [logs, setLogs]       = useState<string[]>([]);
  const esRef                 = useRef<EventSource | null>(null);
  const addLog = useCallback((m: string) => setLogs(p => [...p.slice(-12), m]), []);

  useEffect(() => {
    fetch(`${API}/autoforze/whatsapp/start`, { method: "POST" })
      .then(r => r.json())
      .then(data => {
        if (data.status === "error") { setError(data.message); setStep("error"); return; }
        const es = new EventSource(`${API}/autoforze/whatsapp/qr`);
        esRef.current = es;
        es.onmessage = (evt) => {
          try {
            const ev = JSON.parse(evt.data);
            if (ev.type === "log")           addLog(ev.message);
            if (ev.type === "qr")          { setQr(ev.qr); setStep("qr"); }
            if (ev.type === "authenticated") setStep("authenticated");
            if (ev.type === "ready")       { setPhone(ev.phone); setStep("ready"); es.close(); }
            if (ev.type === "error")       { setError(ev.message); setStep("error"); es.close(); }
          } catch { addLog(evt.data); }
        };
        es.onerror = () => es.close();
      })
      .catch(e => { setError(String(e)); setStep("error"); });
    return () => esRef.current?.close();
  }, [addLog]);

  useEffect(() => {
    if (step === "ready" && phone) {
      const t = setTimeout(() => onAuthenticated(phone), 1500);
      return () => clearTimeout(t);
    }
  }, [step, phone, onAuthenticated]);

  const stepOrder: Record<WaStep, number> = { idle: 0, starting: 1, qr: 2, authenticated: 2, ready: 3, error: 0 };

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xl"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      >
        <motion.div
          className="relative w-[480px] max-w-[95vw] rounded-3xl border border-white/10 bg-[#0f0f1a] shadow-[0_30px_80px_rgba(0,0,0,0.6)] overflow-hidden"
          initial={{ scale: 0.85, y: 40 }} animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.85, y: 40 }} transition={{ type: "spring", damping: 20 }}
        >
          <div className="absolute inset-0 bg-gradient-to-br from-[#25D366]/10 via-transparent to-[#7b61ff]/10 pointer-events-none" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-72 h-40 bg-[#25D366]/15 blur-[80px] pointer-events-none" />

          <div className="flex items-center justify-between px-6 py-5 border-b border-white/5">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-[#25D366]/20"><Smartphone className="w-5 h-5 text-[#25D366]" /></div>
              <div>
                <h3 className="font-bold text-white text-base">WhatsApp Login</h3>
                <p className="text-xs text-gray-400">Required for WhatsApp automation</p>
              </div>
            </div>
            <button onClick={onClose} className="p-1.5 rounded-full hover:bg-white/10 text-gray-400"><X className="w-4 h-4" /></button>
          </div>

          <div className="flex flex-col items-center px-6 py-6 gap-5">
            {/* Steps */}
            <div className="flex items-center gap-2 text-xs w-full">
              {[{ id: "starting", label: "Starting" }, { id: "qr", label: "Scan QR" }, { id: "ready", label: "Connected" }]
                .map((s, i, arr) => {
                  const active = stepOrder[step] >= stepOrder[s.id as WaStep];
                  return (
                    <div key={s.id} className="flex items-center gap-2 flex-1">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ring-2 transition-all ${active ? "bg-[#25D366] ring-[#25D366]/40 text-black" : "bg-white/5 ring-white/10 text-gray-500"}`}>
                        {active ? "✓" : i + 1}
                      </div>
                      <span className={active ? "text-white" : "text-gray-500"}>{s.label}</span>
                      {i < arr.length - 1 && <div className={`flex-1 h-px ${active ? "bg-[#25D366]/50" : "bg-white/10"}`} />}
                    </div>
                  );
                })}
            </div>

            {/* QR area */}
            <div className={`relative rounded-2xl overflow-hidden border-2 p-3 bg-white transition-all ${step === "qr" ? "border-[#25D366] shadow-[0_0_30px_rgba(37,211,102,0.3)]" : "border-white/10"}`}>
              {qrDataUrl && step === "qr" ? (
                <img src={qrDataUrl} alt="WhatsApp QR" className="w-[220px] h-[220px] rounded-lg" />
              ) : step === "ready" ? (
                <div className="w-[220px] h-[220px] flex flex-col items-center justify-center gap-3">
                  <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", damping: 12 }}>
                    <CheckCircle2 className="w-20 h-20 text-[#25D366]" />
                  </motion.div>
                  <span className="text-sm font-semibold text-[#25D366]">Connected!</span>
                  {phone && <span className="text-xs text-gray-500">+{phone}</span>}
                </div>
              ) : step === "error" ? (
                <div className="w-[220px] h-[220px] flex flex-col items-center justify-center gap-3">
                  <X className="w-16 h-16 text-red-500" />
                  <span className="text-xs text-center text-red-500 px-4">{error}</span>
                </div>
              ) : (
                <div className="w-[220px] h-[220px] flex flex-col items-center justify-center gap-4">
                  <Loader2 className="w-12 h-12 text-[#25D366] animate-spin" />
                  <span className="text-sm text-gray-500 text-center">{step === "authenticated" ? "Finalizing…" : "Starting engine…"}</span>
                </div>
              )}
              {step === "authenticated" && (
                <motion.div className="absolute inset-0 bg-[#25D366]/80 flex items-center justify-center rounded-xl" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <Loader2 className="w-10 h-10 text-white animate-spin" />
                </motion.div>
              )}
            </div>

            <div className="text-center text-xs text-gray-400 px-2">
              {step === "qr" ? (
                <><p className="text-sm text-gray-200 font-medium">Open WhatsApp on your phone</p>
                  <p>Tap ⋮ → Linked Devices → Link a Device, then scan the QR</p></>
              ) : step === "ready" ? (
                <p className="text-sm text-[#25D366] font-medium">WhatsApp connected! Building automation…</p>
              ) : step === "error" ? (
                <p className="text-sm text-red-400">Connection failed. Close and try again.</p>
              ) : <p>Initializing secure WhatsApp bridge…</p>}
            </div>

            {logs.length > 0 && (
              <div className="w-full bg-black/40 rounded-xl border border-white/5 px-4 py-3 font-mono text-[10px] text-gray-400 max-h-20 overflow-y-auto">
                {logs.map((l, i) => <div key={i} className={l.includes("[WA]") ? "text-[#25D366]/80" : ""}>{l}</div>)}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Slot Progress Card
// ────────────────────────────────────────────────────────────────────────────
function SlotCard({ slots }: { slots: Slots }) {
  const conf = slots.confidence ?? 0;
  const items = [
    { icon: <Zap className="w-3.5 h-3.5" />,      label: "Trigger",    value: slots.trigger },
    { icon: <ChevronRight className="w-3.5 h-3.5" />, label: "Action", value: slots.action },
    { icon: <Smartphone className="w-3.5 h-3.5" />,   label: "Channel", value: slots.channel },
    { icon: <Info className="w-3.5 h-3.5" />,         label: "Condition", value: slots.condition },
    { icon: <Clock className="w-3.5 h-3.5" />,        label: "Frequency", value: slots.frequency },
  ].filter(i => i.value && i.value !== "null");

  if (items.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3"
    >
      {/* Confidence bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs text-gray-400">
          <span className="flex items-center gap-1"><GitBranch className="w-3 h-3" /> Understanding</span>
          <span className={conf >= 80 ? "text-green-400 font-bold" : "text-[#7b61ff]"}>{conf}%</span>
        </div>
        <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
          <motion.div
            className={`h-full rounded-full ${conf >= 80 ? "bg-green-400" : "bg-gradient-to-r from-[#7b61ff] to-fuchsia-500"}`}
            initial={{ width: 0 }} animate={{ width: `${conf}%` }} transition={{ duration: 0.6 }}
          />
        </div>
      </div>

      {/* Slots */}
      <div className="space-y-2">
        {items.map(it => (
          <div key={it.label} className="flex items-start gap-2">
            <span className="text-[#7b61ff] mt-0.5 shrink-0">{it.icon}</span>
            <div className="min-w-0">
              <span className="text-[10px] uppercase tracking-widest text-gray-500 block">{it.label}</span>
              <span className="text-xs text-gray-200 break-words">{it.value}</span>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Done card
// ────────────────────────────────────────────────────────────────────────────
function DoneCard({ automation }: { automation: Automation }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
      className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 space-y-3"
    >
      <div className="flex items-center gap-2">
        <Rocket className="w-5 h-5 text-green-400" />
        <span className="font-bold text-green-300">{automation.name}</span>
        <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
          {automation.status}
        </span>
      </div>
      <p className="text-xs text-gray-300">{automation.description}</p>
      <div className="space-y-1.5">
        {automation.steps?.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2 text-xs text-gray-400">
            <span className="w-5 h-5 rounded-full bg-white/5 flex items-center justify-center text-[10px] font-bold border border-white/10">{i + 1}</span>
            <span>{s.label}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Suggestions
// ────────────────────────────────────────────────────────────────────────────
const SUGGESTIONS = [
  "When someone sends a WhatsApp message starting with #task, create a task in TaskForze",
  "Every morning at 9am, send me a WhatsApp summary of today's pending tasks",
  "When a task is marked as done, send a WhatsApp celebration message to the team",
  "If I receive a WhatsApp message with 'urgent', create a high-priority task immediately",
];

// ────────────────────────────────────────────────────────────────────────────
// Main component
// ────────────────────────────────────────────────────────────────────────────
export function AutoForzeView() {
  const [messages, setMessages]         = useState<ChatMessage[]>([]);
  const [input, setInput]               = useState("");
  const [loading, setLoading]           = useState(false);
  const [sessionId, setSessionId]       = useState("");
  const [history, setHistory]           = useState<{ role: string; content: string }[]>([]);
  const [slots, setSlots]               = useState<Slots>({});
  const [stage, setStage]               = useState<Stage>("idle");
  const [automation, setAutomation]     = useState<Automation | null>(null);
  const [showWaModal, setShowWaModal]   = useState(false);
  const [waPhone, setWaPhone]           = useState<string | null>(null);
  const [pendingConfirm, setPending]    = useState(false);
  const bottomRef                       = useRef<HTMLDivElement>(null);
  const inputRef                        = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const pushMsg = (role: ChatMessage["role"], content: string, s?: Stage) => {
    setMessages(p => [...p, { id: crypto.randomUUID(), role, content, ts: new Date(), stage: s }]);
  };

  const resetSession = () => {
    if (sessionId) fetch(`${API}/autoforze/converse/${sessionId}`, { method: "DELETE" });
    setMessages([]); setHistory([]); setSlots({}); setStage("idle");
    setSessionId(""); setAutomation(null); setPending(false);
  };

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    setInput("");
    setLoading(true);

    pushMsg("user", text);

    // If the AI reached "confirm" and user said yes → check if WA is needed without WA connected
    const needsWA = slots.channel === "whatsapp" && !waPhone &&
      (stage === "confirm" || pendingConfirm) &&
      ["yes", "go", "build", "confirm", "do it", "sure"].some(w => text.toLowerCase().includes(w));

    if (needsWA) {
      setPending(true);
      setShowWaModal(true);
      setLoading(false);
      return;
    }

    try {
      const updatedHistory = [...history, { role: "user", content: text }];

      const res = await fetch(`${API}/autoforze/converse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: text, history }),
      });

      const data = await res.json();
      setSessionId(data.session_id);
      setSlots(data.slots ?? {});
      setStage(data.stage);

      const assistantHistory = { role: "assistant", content: data.reply };
      setHistory([...updatedHistory, assistantHistory]);
      pushMsg("assistant", data.reply, data.stage);

      if (data.stage === "done" && data.automation?.id) {
        setAutomation(data.automation);
      }
    } catch (err) {
      pushMsg("system", `⚠️ Network error: ${err}`, "error");
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [loading, sessionId, history, slots, stage, waPhone, pendingConfirm]);

  const handleWaAuthenticated = async (phone: string) => {
    setShowWaModal(false);
    setWaPhone(phone);
    setPending(false);
    pushMsg("system", `✅ WhatsApp linked as +${phone}. Building your automation now…`);
    // Re-send a confirmation trigger to finish building
    await sendMessage("yes, confirmed");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  const isWhatsApp = slots.channel === "whatsapp";

  return (
    <>
      {showWaModal && (
        <WhatsAppModal
          onAuthenticated={handleWaAuthenticated}
          onClose={() => { setShowWaModal(false); setPending(false); }}
        />
      )}

      <motion.section
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        className="flex h-[calc(100vh-2rem)] flex-col overflow-hidden rounded-3xl border border-white/10 bg-white/5 shadow-[0_8px_32px_rgba(0,0,0,0.3)] backdrop-blur-3xl relative"
      >
        {/* Background glows */}
        <div className="absolute inset-0 z-0 pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-br from-[#7b61ff]/10 to-transparent opacity-50" />
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#7b61ff]/10 rounded-full blur-[120px] mix-blend-screen animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-[30rem] h-[30rem] bg-fuchsia-600/10 rounded-full blur-[150px] mix-blend-screen animate-pulse delay-700" />
        </div>

        {/* Header */}
        <header className="flex justify-between items-center border-b border-white/10 bg-black/20 px-8 py-5 z-10 backdrop-blur-xl shrink-0">
          <div className="flex items-center gap-4">
            <div className="relative flex h-3 w-3">
              {stage !== "idle" && stage !== "done" && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#7b61ff] opacity-75" />}
              <span className={`relative inline-flex rounded-full h-3 w-3 ${stage === "done" ? "bg-green-400" : stage === "idle" ? "bg-gray-500" : "bg-[#7b61ff]"}`} />
            </div>
            <h2 className="text-xl font-bold text-white tracking-wider flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-[#7b61ff]" />
              AutoForze Builder
            </h2>
            {waPhone && (
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-[#25D366]/15 border border-[#25D366]/30 text-xs text-[#25D366]">
                <Wifi className="w-3 h-3" /> <span>WA +{waPhone}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            {stage !== "idle" && (
              <motion.button
                initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
                onClick={resetSession}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-full border border-white/10 hover:bg-white/10 text-xs text-gray-400 transition-colors"
              >
                <RefreshCw className="w-3 h-3" /> New
              </motion.button>
            )}
          </div>
        </header>

        {/* Body: side-by-side */}
        <div className="flex flex-1 overflow-hidden z-10 gap-0">

          {/* Left: Chat */}
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
              {/* Empty state */}
              {messages.length === 0 && (
                <motion.div
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="h-full flex flex-col items-center justify-center gap-6 text-center pb-10"
                >
                  <div className="relative">
                    <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-[#7b61ff]/30 to-fuchsia-500/30 flex items-center justify-center border border-white/10">
                      <Sparkles className="w-10 h-10 text-[#7b61ff]" />
                    </div>
                    <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-[#7b61ff] rounded-full flex items-center justify-center">
                      <Bot className="w-3.5 h-3.5 text-white" />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-white mb-2">What would you like to automate?</h3>
                    <p className="text-gray-400 text-sm max-w-sm">
                      Describe it in plain English. I'll ask a few questions, then build and deploy it for you.
                    </p>
                  </div>
                  {/* Suggestion chips */}
                  <div className="grid grid-cols-1 gap-2 w-full max-w-lg">
                    {SUGGESTIONS.map((s, i) => (
                      <motion.button
                        key={i} initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.07 }}
                        onClick={() => { setInput(s); inputRef.current?.focus(); }}
                        className="text-left px-4 py-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 hover:border-[#7b61ff]/40 text-xs text-gray-300 transition-all group"
                      >
                        <span className="text-[#7b61ff] mr-2 group-hover:translate-x-1 inline-block transition-transform">→</span>
                        {s}
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              )}

              <AnimatePresence>
                {messages.map(msg => (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.2 }}
                    className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    {msg.role !== "user" && (
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                        msg.role === "system" ? "bg-yellow-500/20 border border-yellow-500/30" : "bg-[#7b61ff]/20 border border-[#7b61ff]/30"
                      }`}>
                        {msg.role === "system" ? <Info className="w-3.5 h-3.5 text-yellow-400" /> : <Bot className="w-3.5 h-3.5 text-[#7b61ff]" />}
                      </div>
                    )}
                    <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-gradient-to-br from-[#7b61ff] to-fuchsia-500 text-white rounded-br-sm"
                        : msg.role === "system"
                        ? "bg-yellow-500/10 border border-yellow-500/20 text-yellow-200 rounded-tl-sm"
                        : "bg-black/40 border border-white/10 text-gray-200 rounded-tl-sm"
                    }`}>
                      {/* Render markdown-style bold */}
                      <div className="whitespace-pre-wrap" dangerouslySetInnerHTML={{
                        __html: msg.content
                          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\n/g, '<br/>')
                      }} />
                      <div className={`text-[10px] mt-1.5 ${msg.role === "user" ? "text-white/50 text-right" : "text-gray-500"}`}>
                        {msg.ts.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </div>
                    {msg.role === "user" && (
                      <div className="w-7 h-7 rounded-full bg-white/10 border border-white/20 flex items-center justify-center shrink-0 mt-0.5">
                        <User className="w-3.5 h-3.5 text-white" />
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>

              {/* Done card */}
              {stage === "done" && automation && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start gap-3">
                  <div className="w-7 h-7" />
                  <div className="max-w-[80%] w-full">
                    <DoneCard automation={automation} />
                  </div>
                </motion.div>
              )}

              {/* Loading indicator */}
              {loading && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
                  <div className="w-7 h-7 rounded-full bg-[#7b61ff]/20 border border-[#7b61ff]/30 flex items-center justify-center shrink-0">
                    <Bot className="w-3.5 h-3.5 text-[#7b61ff]" />
                  </div>
                  <div className="bg-black/40 border border-white/10 rounded-2xl rounded-tl-sm px-4 py-3">
                    <div className="flex gap-1 items-center h-5">
                      {[0, 1, 2].map(i => (
                        <motion.div key={i} className="w-2 h-2 rounded-full bg-[#7b61ff]"
                          animate={{ y: ["0%", "-50%", "0%"] }}
                          transition={{ duration: 0.6, delay: i * 0.15, repeat: Infinity }}
                        />
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              <div ref={bottomRef} className="h-2" />
            </div>

            {/* Input bar */}
            <div className="shrink-0 border-t border-white/10 bg-black/20 px-4 py-4 backdrop-blur-xl">
              <div className={`flex items-end gap-3 rounded-2xl border transition-colors ${
                stage === "done" ? "border-green-500/30 bg-green-500/5" :
                isWhatsApp ? "border-[#25D366]/30 bg-[#25D366]/5" :
                "border-white/10 bg-white/5 focus-within:border-[#7b61ff]/50"
              } p-3`}>
                <textarea
                  ref={inputRef}
                  rows={1}
                  value={input}
                  onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px"; }}
                  onKeyDown={handleKeyDown}
                  disabled={loading || stage === "done"}
                  placeholder={
                    stage === "done" ? "✅ Automation deployed! Click 'New' to create another."
                    : stage === "confirm" ? "Type 'yes' or 'no'…"
                    : messages.length === 0 ? "Describe what you want to automate…"
                    : "Reply to AutoForze…"
                  }
                  className="flex-1 bg-transparent text-white placeholder-gray-500 focus:outline-none text-sm leading-relaxed resize-none min-h-[36px] max-h-[120px]"
                />
                <button
                  onClick={() => sendMessage(input)}
                  disabled={!input.trim() || loading || stage === "done"}
                  className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all disabled:opacity-30 disabled:cursor-not-allowed shrink-0 ${
                    isWhatsApp ? "bg-[#25D366] hover:bg-[#1ea855]" : "bg-gradient-to-br from-[#7b61ff] to-fuchsia-500 hover:opacity-90"
                  }`}
                >
                  <SendHorizonal className="w-4 h-4 text-white" />
                </button>
              </div>
              {stage !== "done" && (
                <p className="text-[10px] text-gray-600 mt-1.5 px-1">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-gray-500 font-mono">Enter</kbd> to send · <kbd className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-gray-500 font-mono">Shift+Enter</kbd> for new line
                </p>
              )}
            </div>
          </div>

          {/* Right: Sidebar */}
          <AnimatePresence>
            {(Object.keys(slots).length > 0 || stage === "done") && (
              <motion.div
                initial={{ width: 0, opacity: 0 }} animate={{ width: 280, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }} transition={{ duration: 0.35 }}
                className="shrink-0 border-l border-white/10 bg-black/20 overflow-hidden"
              >
                <div className="p-5 space-y-4 h-full overflow-y-auto w-[280px]">
                  {/* Header */}
                  <div className="flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-[#7b61ff]" />
                    <span className="text-sm font-semibold text-white">Understanding</span>
                  </div>

                  <SlotCard slots={slots} />

                  {/* Stage badge */}
                  {stage !== "idle" && (
                    <div className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs border ${
                      stage === "done"    ? "bg-green-500/10 border-green-500/30 text-green-300" :
                      stage === "confirm" ? "bg-yellow-500/10 border-yellow-500/30 text-yellow-300" :
                      "bg-[#7b61ff]/10 border-[#7b61ff]/30 text-[#a78bfa]"
                    }`}>
                      <div className={`w-1.5 h-1.5 rounded-full ${
                        stage === "done" ? "bg-green-400" : stage === "confirm" ? "bg-yellow-400 animate-pulse" : "bg-[#7b61ff] animate-pulse"
                      }`} />
                      {stage === "done" ? "✓ Deployed" : stage === "confirm" ? "⚡ Ready to build" : "🔍 Gathering info"}
                    </div>
                  )}

                  {/* Tips */}
                  {stage === "confirm" && (
                    <div className="text-xs text-gray-400 bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-3 space-y-1">
                      <p className="text-yellow-300 font-medium">Ready to forge!</p>
                      <p>Type <strong className="text-white">yes</strong> to build, or describe any changes.</p>
                    </div>
                  )}

                  {stage === "done" && automation && (
                    <div className="text-xs text-gray-400 bg-green-500/5 border border-green-500/20 rounded-xl p-3 space-y-1">
                      <p className="text-green-300 font-medium">🚀 Live!</p>
                      <p>Automation ID: <code className="text-white font-mono text-[10px]">{automation.id.slice(0, 8)}…</code></p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.section>
    </>
  );
}
