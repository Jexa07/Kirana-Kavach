import { useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Bell,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  MessageSquare,
  Mic,
  ShieldCheck,
  Sparkles,
  Store,
  TrendingDown,
  User,
  Volume2,
  VolumeX,
} from "lucide-react";
import "./App.css";
import { PlansModal } from "./PlansModal";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const MERCHANT_ID = "M1001";

type CopilotState =
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "INSIGHT_FOUND"
  | "REVIEW_ACTION"
  | "APPROVING"
  | "ACTION_PREPARED"
  | "REJECTED";

type AudioState = "IDLE" | "PREPARING" | "PLAYING" | "FINISHED" | "ERROR";

interface TransactionRecord {
  transaction_id: string;
  amount: number;
  timestamp: string;
  payment_mode: string;
}

interface CustomerLeak {
  type: "customer_frequency_drop";
  customer_id: string;
  normal_purchase_gap_days: number;
  current_gap_days: number;
  ratio_vs_normal: number;
  last_purchase: string;
  total_purchases?: number;
  total_spent?: number;
  average_ticket?: number;
  preferred_payment_mode?: string;
  recent_transactions?: TransactionRecord[];
  rule?: string;
}

interface ActionPayload {
  customer_id?: string;
  transaction_ids?: string[];
  pending_amount?: number;
  channel?: string;
  message?: string;
  campaign_type?: string;
  payment_link_mode?: string;
}

interface ActionContract {
  type: "CREATE_PAYTM_SUPPORT_CASE" | "DRAFT_CUSTOMER_MESSAGE";
  description: string;
  requires_confirmation: boolean;
  payload: ActionPayload;
}

interface ReasoningData {
  explanation: string;
  recommendation: string;
  action: ActionContract;
}

interface VoiceResponse {
  merchant_id: string;
  transcript: string;
  detected_language: string;
  selected_leak_type: string;
  memory_items_found: number;
  spoken_text: string;
  leak?: CustomerLeak | any;
  reasoning: ReasoningData;
  audio: null | string;
}

interface ExecutionResult {
  merchant_id: string;
  action_type: string;
  status: string;
  external_id?: string;
  outcome_note: string;
  executed_at?: string;
  provider: string;
  campaign_type?: string;
  customer_id?: string;
  message?: string;
  payment_link_reference?: string;
  confirmation_source?: string;
  channel?: string;
  message_sid?: string;
  recipient?: string;
  template_sid?: string;
  draft_message?: string;
  error_code?: string | number;
}

interface ActionConfirmResponse {
  merchant_id: string;
  status: string;
  action: ActionContract;
  execution?: ExecutionResult;
}

const formatDate = (isoString?: string) => {
  if (!isoString) return "N/A";
  try {
    const d = new Date(isoString);
    return (
      d.toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }) +
      " " +
      d.toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      })
    );
  } catch {
    return isoString;
  }
};

const getGreetingTime = () => {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
};

function App() {
  const [copilotState, setCopilotState] = useState<CopilotState>("IDLE");
  const [transcript, setTranscript] = useState<string>("");
  const [error, setError] = useState<string>("");

  const [voiceData, setVoiceData] = useState<VoiceResponse | null>(null);
  const [initialLeak, setInitialLeak] = useState<CustomerLeak | null>(null);
  const [editableMessage, setEditableMessage] = useState<string>("");
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);
  const [lastExecutionResult, setLastExecutionResult] = useState<ExecutionResult | null>(null);

  const [audioState, setAudioState] = useState<AudioState>("IDLE");
  const [audioError, setAudioError] = useState<string>("");

  // Plans Modal state (default to growth plan)
  const [isPlansModalOpen, setIsPlansModalOpen] = useState<boolean>(false);
  const [currentPlan, setCurrentPlan] = useState<string>("growth");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cachedAudioBase64Ref = useRef<string | null>(null);

  // Dynamically fetch detected leaks on mount
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/merchants/${MERCHANT_ID}/leaks`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.customer_frequency_leaks?.length) {
          setInitialLeak(data.customer_frequency_leaks[0]);
        }
      })
      .catch((err) => console.error("Error fetching initial leaks:", err));
  }, []);

  const activeLeak = voiceData?.leak || initialLeak;

  const resetFlow = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setAudioState("IDLE");
    setAudioError("");
    cachedAudioBase64Ref.current = null;

    setCopilotState("IDLE");
    setTranscript("");
    setError("");
    setVoiceData(null);
    setEditableMessage("");
    setExecutionResult(null);
  };

  const handlePlayAudio = async () => {
    if (!voiceData || !voiceData.spoken_text) return;

    if (audioState === "PLAYING" && audioRef.current) {
      audioRef.current.pause();
      setAudioState("FINISHED");
      return;
    }

    setAudioError("");

    try {
      let audioBase64 = cachedAudioBase64Ref.current;

      if (!audioBase64) {
        setAudioState("PREPARING");
        const response = await fetch(
          `${API_BASE_URL}/api/merchants/${MERCHANT_ID}/tts`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              text: voiceData.spoken_text,
              language: voiceData.detected_language,
            }),
          }
        );

        if (!response.ok) {
          const message = await response.text();
          throw new Error(`TTS failed (${response.status}): ${message}`);
        }

        const ttsData = await response.json();
        if (!ttsData.audio || !ttsData.audio.audio_base64) {
          throw new Error("No audio payload returned from backend.");
        }

        audioBase64 = ttsData.audio.audio_base64;
        cachedAudioBase64Ref.current = audioBase64;
      }

      const audioSrc = `data:audio/wav;base64,${audioBase64}`;
      const audio = new Audio(audioSrc);
      audioRef.current = audio;

      audio.onended = () => {
        setAudioState("FINISHED");
      };

      audio.onerror = (e) => {
        console.error("[TTS AUDIO PLAYBACK ERROR]", e);
        setAudioError("Audio playback failed.");
        setAudioState("ERROR");
      };

      setAudioState("PLAYING");
      await audio.play();
    } catch (err) {
      console.error("[TTS FETCH ERROR]", err);
      setAudioError(
        err instanceof Error ? err.message : "Failed to load audio."
      );
      setAudioState("ERROR");
    }
  };

  const handleVoice = async () => {
    setError("");

    if (copilotState === "LISTENING") {
      mediaRecorderRef.current?.stop();
      return;
    }

    resetFlow();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = MediaRecorder.isTypeSupported(
        "audio/webm;codecs=opus",
      )
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;

        const audioBlob = new Blob(chunksRef.current, {
          type: "audio/webm",
        });

        if (audioBlob.size === 0) {
          setError("No audio was captured. Please try again.");
          setCopilotState("IDLE");
          return;
        }

        try {
          setCopilotState("THINKING");

          const formData = new FormData();
          formData.append(
            "audio",
            audioBlob,
            "merchant-voice.webm",
          );

          const response = await fetch(
            `${API_BASE_URL}/api/merchants/${MERCHANT_ID}/voice?include_tts=false`,
            {
              method: "POST",
              body: formData,
            },
          );

          if (!response.ok) {
            const message = await response.text();
            throw new Error(
              `Voice request failed (${response.status}): ${message}`,
            );
          }

          const data: VoiceResponse = await response.json();
          console.log("[KAVACH VOICE RESPONSE]", data);

          setVoiceData(data);
          setEditableMessage(data.reasoning?.action?.payload?.message || "");
          setTranscript(data.transcript || "Voice processed successfully.");
          setCopilotState("INSIGHT_FOUND");
        } catch (err) {
          console.error(err);
          setError(
            err instanceof Error
              ? err.message
              : "Something went wrong while processing your voice.",
          );
          setCopilotState("IDLE");
        }
      };

      recorder.start();
      setCopilotState("LISTENING");
    } catch (err) {
      console.error(err);
      setError("Microphone access was denied or unavailable.");
      setCopilotState("IDLE");
    }
  };

  const handleConfirmAction = async (approved: boolean) => {
    if (!voiceData) return;

    setError("");
    setCopilotState("APPROVING");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/merchants/${MERCHANT_ID}/actions/confirm`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            action_type: voiceData.reasoning.action.type,
            approved: approved,
            confirmation_source: "ui",
            message: editableMessage || voiceData.reasoning.action.payload.message,
          }),
        },
      );

      if (!response.ok) {
        const message = await response.text();
        throw new Error(
          `Action confirmation failed (${response.status}): ${message}`,
        );
      }

      const data: ActionConfirmResponse = await response.json();
      console.log("[KAVACH ACTION CONFIRMATION RESPONSE]", data);

      if (approved && data.execution) {
        setExecutionResult(data.execution);
        setLastExecutionResult(data.execution);
        setCopilotState("ACTION_PREPARED");
      } else {
        setCopilotState("REJECTED");
      }
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error
          ? err.message
          : "Failed to confirm action with backend.",
      );
      setCopilotState("INSIGHT_FOUND");
    }
  };

  const renderStatusText = () => {
    switch (copilotState) {
      case "LISTENING":
        return "Listening to shop...";
      case "THINKING":
        return "Thinking...";
      case "INSIGHT_FOUND":
        return "Insight detected";
      case "REVIEW_ACTION":
        return "Reviewing action";
      case "APPROVING":
        return "Processing...";
      case "ACTION_PREPARED":
        return "Action completed";
      case "REJECTED":
        return "Action declined";
      default:
        return "Ready";
    }
  };

  return (
    <div className="app">
      {/* Merchant Top Header */}
      <header className="topbar">
        <div className="topbar-content">
          <div
            className="brand"
            onClick={resetFlow}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && resetFlow()}
            title="Reset to home dashboard"
          >
            <div className="brand-icon">
              <ShieldCheck size={20} />
            </div>
            <div className="brand-text">
              <h1>Kirana Kavach</h1>
              <p>Sharma General Store · Mumbai</p>
            </div>
          </div>

          <div className="header-right">
            {/* Subtle Paytm Secondary Logo Badge */}
            <div className="paytm-header-pill" title="Paytm Merchant Acceptance Partner">
              <svg width="40" height="12" viewBox="0 0 120 36" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path fill="#ffffff" d="M14.2 4H2.4v28h5.2V21.4h6.6c5.8 0 10.4-4.2 10.4-10.2S20 4 14.2 4zm-.4 12.8H7.6V8.6h6.2c3 0 5.4 1.8 5.4 4.1s-2.4 4.1-5.4 4.1zM34.8 12.2c-3.8 0-6.6 2.6-6.6 7.4 0 4.8 2.8 7.4 6.6 7.4 3.4 0 5.6-2 6.2-4.8h-4.8c-.4 1.2-1.2 1.8-2 1.8-1.4 0-2.4-1.2-2.4-3.6h9.6v-1.4c0-4.6-2.6-6.8-6.6-6.8zm-2.2 5.4c.2-1.6 1.2-2.6 2.2-2.6s2 .8 2.2 2.6h-4.4zM53.4 12.6l-4.4 11-4.4-11h-5.4l7.2 16.4-3.2 7h5.2l10.4-23.4h-5.4z"/>
                <path fill="#00baf2" d="M72.4 4h-6v4.6h6V4zm-6 8.6v19.4h6V12.6h-6zm25.8 0c-3.2 0-5.4 1.4-6.4 3.2v-2.8h-5.6v19.4h6v-11c0-2.4 1.6-3.8 3.8-3.8s3.4 1.4 3.4 3.8v11h6V19.8c0-4.8-2.8-7.2-7.2-7.2z"/>
              </svg>
            </div>

            <div className="status-pill">
              <span
                className={`status-dot ${
                  copilotState === "LISTENING"
                    ? "listening"
                    : copilotState === "THINKING" || copilotState === "APPROVING"
                    ? "thinking"
                    : copilotState === "ACTION_PREPARED"
                    ? "success"
                    : ""
                }`}
              />
              <span>{renderStatusText()}</span>
            </div>

            {/* Explore Plans Header Button */}
            <button
              className="explore-plans-btn"
              onClick={() => setIsPlansModalOpen(true)}
              title="Explore Kirana Kavach subscription plans"
            >
              <Sparkles size={13} className="explore-plans-icon" />
              <span className="explore-plans-text">Explore Plans</span>
            </button>

            <button
              className="header-icon-btn"
              aria-label="View notifications"
              title="Notifications"
            >
              <Bell size={17} />
            </button>

            <button
              className="merchant-profile-avatar-btn"
              aria-label="Merchant account profile"
              title="Rakesh Sharma · Sharma General Store"
            >
              S
            </button>
          </div>
        </div>
      </header>

      {/* Spoken Pill Banner */}
      {(copilotState === "INSIGHT_FOUND" ||
        copilotState === "REVIEW_ACTION" ||
        copilotState === "APPROVING" ||
        copilotState === "ACTION_PREPARED" ||
        copilotState === "REJECTED") && (
        <div className="spoken-pill-container">
          <div className="spoken-pill">
            <Mic size={14} />
            <span>"{transcript || voiceData?.spoken_text || "मेरी दुकान पे ग्राहक कम आ रहे हैं"}"</span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main className="main-content">
        {/* Error Banner */}
        {error && (
          <div className="error-banner" role="alert">
            <AlertCircle size={18} />
            <div>
              <span>System Notification</span>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* ================================================= */}
        {/* 1. DASHBOARD / IDLE HOME VIEW                     */}
        {/* ================================================= */}
        {(copilotState === "IDLE" ||
          copilotState === "LISTENING" ||
          copilotState === "THINKING") && (
          <div className="dashboard-home">
            {/* Merchant Greeting Header */}
            <div className="greeting-card">
              <div className="greeting-text">
                <h2>{getGreetingTime()}, Sharma General Store</h2>
                <p>Here's what needs your attention today in your shop.</p>
              </div>
              <div className="greeting-date">
                <Calendar size={13} style={{ marginRight: 6, display: "inline" }} />
                Today, {new Date().toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}
              </div>
            </div>

            {/* Primary 2-Column Merchant Grid */}
            <div className="dashboard-grid">
              {/* Left Column: Attention Card + Voice Panel */}
              <div className="dashboard-main-col">
                {/* Primary Attention Hero Card */}
                <section className="attention-hero-card">
                  <div className="hero-badge-row">
                    <span className="attention-badge">
                      <TrendingDown size={13} />
                      NEEDS YOUR ATTENTION
                    </span>
                    <span className="priority-pill">High Priority</span>
                  </div>

                  <div className="attention-hero-body">
                    <h3 className="attention-title">Customer visit frequency drop</h3>
                    <p className="attention-desc">
                      {activeLeak ? (
                        <>
                          Regular customer <strong>{activeLeak.customer_id}</strong> has lapsed visits. Usually visits every <strong>~{activeLeak.normal_purchase_gap_days} days</strong>, but has been absent for <strong>~{activeLeak.current_gap_days} days</strong> ({activeLeak.ratio_vs_normal}× longer than normal).
                        </>
                      ) : (
                        "Monitoring customer visit frequency patterns across recent transaction history."
                      )}
                    </p>

                    <div className="attention-metrics-strip">
                      <div className="strip-item">
                        <span className="strip-label">Customer</span>
                        <span className="strip-val text-navy">
                          {activeLeak ? activeLeak.customer_id : "—"}
                        </span>
                      </div>
                      <div className="strip-divider" />
                      <div className="strip-item">
                        <span className="strip-label">Usual Gap</span>
                        <span className="strip-val text-navy">
                          {activeLeak?.normal_purchase_gap_days
                            ? `~${activeLeak.normal_purchase_gap_days} days`
                            : "—"}
                        </span>
                      </div>
                      <div className="strip-divider" />
                      <div className="strip-item">
                        <span className="strip-label">Current Gap</span>
                        <span className="strip-val text-amber">
                          {activeLeak?.current_gap_days
                            ? `~${activeLeak.current_gap_days} days`
                            : "—"}
                        </span>
                      </div>
                      <div className="strip-divider" />
                      <div className="strip-item">
                        <span className="strip-label">Multiplier</span>
                        <span className="strip-val text-amber">
                          {activeLeak?.ratio_vs_normal
                            ? `${activeLeak.ratio_vs_normal}× gap`
                            : "—"}
                        </span>
                      </div>
                    </div>

                    <div className="attention-cta-row">
                      <button
                        className="btn-talk-attention"
                        onClick={handleVoice}
                        disabled={copilotState === "THINKING"}
                      >
                        <span>Review customer</span>
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  </div>
                </section>

                {/* Voice Assistant Panel */}
                <section className="voice-assistant-panel">
                  <div className="voice-panel-header">
                    <div className="voice-badge">
                      <Sparkles size={13} />
                      <span>KAVACH VOICE ASSISTANT</span>
                    </div>
                    <span className="voice-status-tag">
                      {copilotState === "LISTENING" ? "Mic Active" : "Ready"}
                    </span>
                  </div>

                  <div className="voice-panel-body">
                    <button
                      className={`voice-orb-button ${
                        copilotState === "LISTENING"
                          ? "listening"
                          : copilotState === "THINKING"
                          ? "thinking"
                          : ""
                      }`}
                      onClick={handleVoice}
                      disabled={copilotState === "THINKING"}
                      aria-label="Talk to Kavach voice assistant"
                    >
                      {copilotState === "THINKING" ? (
                        <Loader2 size={30} className="spin-slow" />
                      ) : copilotState === "LISTENING" ? (
                        <div className="equalizer-bars-sm">
                          <span className="eq-bar-sm eq-1" />
                          <span className="eq-bar-sm eq-2" />
                          <span className="eq-bar-sm eq-3" />
                          <span className="eq-bar-sm eq-4" />
                        </div>
                      ) : (
                        <Mic size={30} />
                      )}
                    </button>

                    <div className="voice-panel-info">
                      <h3>
                        {copilotState === "THINKING"
                          ? "Kavach is thinking..."
                          : copilotState === "LISTENING"
                          ? "Listening to your shop..."
                          : "Talk to Kavach"}
                      </h3>
                      <p>
                        {copilotState === "THINKING"
                          ? "Analyzing shop transaction patterns & customer history"
                          : copilotState === "LISTENING"
                          ? transcript
                            ? `"${transcript}"`
                            : "Speak now. Kavach is listening..."
                          : "Tell me what is happening in your shop"}
                      </p>

                      <div
                        className="voice-prompt-pill"
                        onClick={handleVoice}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => e.key === "Enter" && handleVoice()}
                        title="Click to record this query"
                      >
                        <div className="prompt-meta">TRY SAYING</div>
                        <div className="prompt-hi">"मेरी दुकान पे ग्राहक कम आ रहे हैं"</div>
                      </div>
                    </div>
                  </div>
                </section>
              </div>

              {/* Right Column: Today's Priorities + Shop Status */}
              <div className="dashboard-side-col">
                <section className="priorities-card">
                  <div className="side-card-header">
                    <h3>Today's Priorities</h3>
                    <span className="priorities-count">3 items</span>
                  </div>

                  <div className="priorities-list">
                    <div className="priority-item">
                      <div className="priority-icon-box icon-amber">
                        <TrendingDown size={16} />
                      </div>
                      <div className="priority-content">
                        <div className="priority-title">Customer retention</div>
                        <div className="priority-status text-amber">1 action needs your review</div>
                        <div className="priority-desc">
                          {activeLeak
                            ? `Lapsed visit detected for regular buyer ${activeLeak.customer_id}.`
                            : "Monitoring customer visit frequency drops."}
                        </div>
                      </div>
                    </div>

                    <div className="priority-item">
                      <div className="priority-icon-box icon-purple">
                        <Sparkles size={16} />
                      </div>
                      <div className="priority-content">
                        <div className="priority-title">Past actions</div>
                        <div className="priority-status text-purple">Kavach remembers what worked</div>
                        <div className="priority-desc">Customer preferences & past offers saved.</div>
                      </div>
                    </div>

                    <div className="priority-item">
                      <div className="priority-icon-box icon-green">
                        <CheckCircle2 size={16} />
                      </div>
                      <div className="priority-content">
                        <div className="priority-title">Ready to act</div>
                        <div className="priority-status text-green">WhatsApp action available</div>
                        <div className="priority-desc">Actions require merchant approval before dispatch.</div>
                      </div>
                    </div>
                  </div>
                </section>

                {/* Shop Location & Connectivity */}
                <section className="shop-info-card">
                  <div className="shop-info-header">
                    <Store size={16} className="shop-icon" />
                    <div>
                      <h4>Sharma General Store</h4>
                      <p>Mumbai Central · Active Merchant</p>
                    </div>
                  </div>
                  <div className="shop-status-footer">
                    <span className="status-indicator-dot" />
                    <span>Connected & Ready</span>
                  </div>
                </section>
              </div>
            </div>

            {/* Recent Activity Section */}
            <section className="recent-activity-section">
              <div className="section-header">
                <div className="section-header-left">
                  <Activity size={16} />
                  <h3>Recent Activity</h3>
                </div>
                {lastExecutionResult && (
                  <span className="activity-status-badge">1 Action Executed</span>
                )}
              </div>

              {lastExecutionResult ? (
                <div className="activity-item-card">
                  <div className="activity-icon-box">
                    <CheckCircle2 size={18} />
                  </div>
                  <div className="activity-details">
                    <div className="activity-title-row">
                      <span className="activity-title">
                        {lastExecutionResult.status === "queued"
                          ? "WhatsApp reactivation queued"
                          : "Action executed"}
                      </span>
                      <span className="activity-time">
                        {formatDate(lastExecutionResult.executed_at || new Date().toISOString())}
                      </span>
                    </div>
                    <p className="activity-sub">
                      Customer: <strong className="mono">{lastExecutionResult.customer_id || activeLeak?.customer_id || "Customer"}</strong> · Recipient: <strong className="mono">{lastExecutionResult.recipient || "Customer"}</strong> · Provider: <strong style={{ textTransform: "capitalize" }}>{lastExecutionResult.provider || "Twilio"}</strong>
                    </p>
                  </div>
                </div>
              ) : (
                <div className="activity-empty-card">
                  <Clock size={18} className="empty-icon" />
                  <div className="empty-text">
                    <h4>No recent actions executed today</h4>
                    <p>When you approve customer reactivation or support requests, your action history will appear here.</p>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}

        {/* ================================================= */}
        {/* 2. INSIGHT FOUND VIEW                             */}
        {/* ================================================= */}
        {voiceData && copilotState === "INSIGHT_FOUND" && (
          <section className="insight-container">
            <div className="card-header-badge">
              <Sparkles size={13} />
              <span>BUSINESS INSIGHT</span>
            </div>

            <div className="customer-row">
              <span className="meta-label">Customer Activity</span>
              <span className="meta-val">
                <User size={15} style={{ marginRight: 6, display: "inline" }} />
                {voiceData.leak?.customer_id ||
                  voiceData.reasoning.action.payload.customer_id ||
                  "Customer"}
              </span>
            </div>

            <h3 className="insight-title">
              {voiceData.reasoning.explanation ||
                "Regular customer visits have dropped significantly from their usual frequency."}
            </h3>

            {/* Dynamic metrics comparative box */}
            {voiceData.leak && (
              <div className="leak-metrics-box">
                <div className="metric-col">
                  <span className="metric-label">Usually</span>
                  <span className="metric-val text-navy">
                    {voiceData.leak.normal_purchase_gap_days
                      ? `Every ~${voiceData.leak.normal_purchase_gap_days} days`
                      : "Regular frequency"}
                  </span>
                </div>
                <span className="arrow-sep">→</span>
                <div className="metric-col">
                  <span className="metric-label">Now</span>
                  <span className="metric-val text-amber">
                    {voiceData.leak.current_gap_days
                      ? `~${voiceData.leak.current_gap_days} days`
                      : "Delayed"}
                    {voiceData.leak.ratio_vs_normal ? ` (${voiceData.leak.ratio_vs_normal}×)` : ""}
                  </span>
                </div>
              </div>
            )}

            <div className="rec-section">
              <div className="rec-label">RECOMMENDED ACTION</div>
              <div className="rec-text">{voiceData.reasoning.recommendation}</div>
            </div>

            <div className="insight-actions">
              <button
                className="btn-audio-listen"
                onClick={handlePlayAudio}
                disabled={audioState === "PREPARING"}
              >
                {audioState === "PREPARING" ? (
                  <>
                    <Loader2 size={15} className="spin-slow" />
                    <span>Preparing audio...</span>
                  </>
                ) : audioState === "PLAYING" ? (
                  <>
                    <Volume2 size={15} />
                    <span>Speaking...</span>
                  </>
                ) : audioState === "ERROR" ? (
                  <>
                    <VolumeX size={15} />
                    <span>{audioError || "Try again"}</span>
                  </>
                ) : (
                  <>
                    <Volume2 size={15} />
                    <span>Listen to audio</span>
                  </>
                )}
              </button>

              <button
                className="btn-review-primary"
                onClick={() => setCopilotState("REVIEW_ACTION")}
              >
                Review action
                <ArrowRight size={15} />
              </button>
            </div>
          </section>
        )}

        {/* ================================================= */}
        {/* 3. CUSTOMER REVIEW VIEW                           */}
        {/* ================================================= */}
        {voiceData &&
          (copilotState === "REVIEW_ACTION" || copilotState === "APPROVING") && (
            <section className="review-container">
              <div className="card-header-badge">
                <FileText size={13} />
                <span>REVIEW BEFORE SENDING</span>
              </div>

              <div className="customer-row">
                <span className="meta-label">Customer Profile</span>
                <span className="meta-val">
                  <User size={15} style={{ marginRight: 6, display: "inline" }} />
                  {voiceData.leak?.customer_id ||
                    voiceData.reasoning.action.payload.customer_id ||
                    "Customer"}
                </span>
              </div>

              {/* Rich Customer Metrics Grid */}
              <div className="customer-metrics-grid">
                <div className="metric-card-sm">
                  <span className="sm-label">Last Visit</span>
                  <span className="sm-val">
                    {formatDate(voiceData.leak?.last_purchase)}
                  </span>
                </div>
                <div className="metric-card-sm">
                  <span className="sm-label">Total Visits</span>
                  <span className="sm-val">
                    {voiceData.leak?.total_purchases != null
                      ? `${voiceData.leak.total_purchases} visits`
                      : "N/A"}
                  </span>
                </div>
                <div className="metric-card-sm">
                  <span className="sm-label">Total Spend</span>
                  <span className="sm-val">
                    {voiceData.leak?.total_spent != null
                      ? `₹${voiceData.leak.total_spent.toLocaleString("en-IN")}`
                      : "N/A"}
                  </span>
                </div>
                <div className="metric-card-sm">
                  <span className="sm-label">Avg Ticket</span>
                  <span className="sm-val">
                    {voiceData.leak?.average_ticket != null
                      ? `₹${voiceData.leak.average_ticket.toLocaleString("en-IN")}`
                      : "N/A"}
                  </span>
                </div>
                <div className="metric-card-sm">
                  <span className="sm-label">Pay Mode</span>
                  <span className="sm-val">
                    {voiceData.leak?.preferred_payment_mode || "UPI"}
                  </span>
                </div>
                <div className="metric-card-sm">
                  <span className="sm-label">Usual Frequency</span>
                  <span className="sm-val">
                    {voiceData.leak?.normal_purchase_gap_days != null
                      ? `Every ~${voiceData.leak.normal_purchase_gap_days}d`
                      : "N/A"}
                  </span>
                </div>
                <div className="metric-card-sm">
                  <span className="sm-label">Current Gap</span>
                  <span className="sm-val highlight-gold">
                    {voiceData.leak?.current_gap_days != null
                      ? `~${voiceData.leak.current_gap_days}d (${voiceData.leak.ratio_vs_normal}×)`
                      : "N/A"}
                  </span>
                </div>
              </div>

              {/* Recent Transaction Timeline */}
              {voiceData.leak?.recent_transactions &&
                voiceData.leak.recent_transactions.length > 0 && (
                  <div className="recent-history-section">
                    <span className="meta-label">Recent Paytm Purchase History</span>
                    <div className="recent-history-list">
                      {voiceData.leak.recent_transactions.map((tx: TransactionRecord) => (
                        <div key={tx.transaction_id} className="history-item">
                          <div className="history-left">
                            <span className="history-txn-id">{tx.transaction_id}</span>
                            <span className="history-mode-badge">{tx.payment_mode}</span>
                          </div>
                          <div className="history-right">
                            <span className="history-date">
                              {formatDate(tx.timestamp)}
                            </span>
                            <span className="history-amount">₹{tx.amount}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Editable Suggested Message */}
              <div className="draft-message-section">
                <span className="meta-label">Suggested Message (Editable)</span>
                <div className="hindi-message-box editable-box">
                  <MessageSquare size={16} className="msg-icon" />
                  <textarea
                    className="editable-message-input"
                    value={editableMessage}
                    onChange={(e) => setEditableMessage(e.target.value)}
                    placeholder="Type or review customer message..."
                    rows={3}
                  />
                </div>
              </div>

              <div className="chips-row">
                <span className="chip">Customer reactivation</span>
                <span className="chip">Merchant review</span>
                <span className="chip">Demo payment link</span>
              </div>

              <div className="disclaimer-pill">
                <ShieldCheck size={15} />
                <span>WhatsApp sending is triggered only after merchant approval.</span>
              </div>

              <div className="review-button-group">
                <button
                  className="btn-not-now"
                  onClick={() => handleConfirmAction(false)}
                  disabled={copilotState === "APPROVING"}
                >
                  Not now
                </button>

                <button
                  className="btn-approve-primary"
                  onClick={() => handleConfirmAction(true)}
                  disabled={copilotState === "APPROVING"}
                >
                  {copilotState === "APPROVING" ? (
                    <>
                      <Loader2 size={15} className="spin-slow" />
                      <span>Processing...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={15} />
                      <span>Approve & Send</span>
                    </>
                  )}
                </button>
              </div>
            </section>
          )}

        {/* ================================================= */}
        {/* 4. SUCCESS VIEW                                   */}
        {/* ================================================= */}
        {copilotState === "ACTION_PREPARED" && executionResult && (
          <section className="success-container">
            <div className="success-badge">
              <CheckCircle2 size={13} />
              <span>
                {executionResult.status === "queued"
                  ? "WHATSAPP QUEUED"
                  : executionResult.status === "executed"
                  ? "ACTION EXECUTED"
                  : executionResult.status === "failed"
                  ? "ACTION FAILED"
                  : "ACTION PREPARED"}
              </span>
            </div>

            <h3 className="success-title">
              {executionResult.status === "queued"
                ? "WhatsApp message queued"
                : executionResult.status === "executed"
                ? "Paytm support case created"
                : executionResult.status === "failed"
                ? "WhatsApp delivery failed"
                : "Customer reactivation pack prepared"}
            </h3>
            <p className="success-sub">
              {executionResult.outcome_note || "Prepared for merchant review."}
            </p>

            <div className="meta-table">
              <div className="table-row">
                <span>Customer</span>
                <strong>{executionResult.customer_id || "Customer"}</strong>
              </div>
              {executionResult.recipient && (
                <div className="table-row">
                  <span>Recipient</span>
                  <strong className="mono">{executionResult.recipient}</strong>
                </div>
              )}
              <div className="table-row">
                <span>Campaign</span>
                <strong>
                  {executionResult.campaign_type === "customer_reactivation"
                    ? "Customer reactivation"
                    : executionResult.campaign_type || "N/A"}
                </strong>
              </div>
              <div className="table-row">
                <span>Provider</span>
                <strong style={{ textTransform: "capitalize" }}>
                  {executionResult.provider || "n8n"}
                </strong>
              </div>
              {executionResult.template_sid && (
                <div className="table-row">
                  <span>Template</span>
                  <strong className="mono">{executionResult.template_sid}</strong>
                </div>
              )}
              <div className="table-row">
                <span>Message ID / Ref</span>
                <strong className="mono">
                  {executionResult.message_sid || executionResult.external_id || "N/A"}
                </strong>
              </div>
              {executionResult.payment_link_reference && (
                <div className="table-row">
                  <span>Payment Link</span>
                  <strong className="mono">{executionResult.payment_link_reference}</strong>
                </div>
              )}
            </div>

            {(executionResult.message || executionResult.draft_message) && (
              <div className="approved-message-card">
                <span className="meta-label">Approved Message</span>
                <p>"{executionResult.message || executionResult.draft_message}"</p>
                {executionResult.provider === "twilio" && (
                  <p className="trial-template-note">
                    ℹ️ Your WhatsApp reactivation message was submitted to Twilio using the configured trial template. AI draft kept for merchant record.
                  </p>
                )}
              </div>
            )}

            <div className="disclaimer-pill">
              <ShieldCheck size={15} />
              <span>WhatsApp sending was triggered only after your explicit approval.</span>
            </div>

            <div className="memory-badge">
              🧠 Customer reactivation outcome saved
            </div>

            <button className="btn-start-over" onClick={resetFlow}>
              Start over
            </button>
          </section>
        )}

        {/* ================================================= */}
        {/* 5. REJECTED VIEW                                  */}
        {/* ================================================= */}
        {copilotState === "REJECTED" && (
          <section className="rejected-container">
            <div className="rejected-icon">
              <Clock size={22} />
            </div>

            <h3>Okay. I won't take this action.</h3>
            <p>I'll keep this in mind for next time.</p>

            <button className="btn-start-over" onClick={resetFlow}>
              Talk to Kavach again
            </button>
          </section>
        )}

        {/* Clean Footer Trust Bar (No landing-page carousel dots) */}
        <div className="footer-trust-bar">
          <div className="trust-items">
            <span>🧠 Remembers past shop actions</span>
            <span>🔒 Merchant approval required for all actions</span>
          </div>
        </div>
      </main>

      {/* Plans & Pricing Modal */}
      <PlansModal
        isOpen={isPlansModalOpen}
        onClose={() => setIsPlansModalOpen(false)}
        currentPlan={currentPlan}
        onSelectPlan={(planId) => {
          setCurrentPlan(planId);
        }}
      />
    </div>
  );
}

export default App;