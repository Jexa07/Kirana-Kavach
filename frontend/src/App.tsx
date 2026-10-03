import { useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  MessageSquare,
  Mic,
  ShieldCheck,
  Sparkles,
  User,
  Volume2,
  VolumeX,
} from "lucide-react";
import "./App.css";

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
  reasoning: ReasoningData;
  audio: null | string;
}

interface ExecutionResult {
  merchant_id: string;
  action_type: string;
  status: "executed" | "prepared" | "rejected";
  external_id?: string;
  outcome_note: string;
  executed_at?: string;
  provider: string;
  campaign_type?: string;
  customer_id?: string;
  message?: string;
  payment_link_reference?: string;
  confirmation_source?: string;
}

interface ActionConfirmResponse {
  merchant_id: string;
  status: "executed" | "prepared" | "rejected";
  action: ActionContract;
  execution?: ExecutionResult;
}

function App() {
  const [copilotState, setCopilotState] = useState<CopilotState>("IDLE");
  const [transcript, setTranscript] = useState<string>("");
  const [error, setError] = useState<string>("");

  const [voiceData, setVoiceData] = useState<VoiceResponse | null>(null);
  const [executionResult, setExecutionResult] = useState<ExecutionResult | null>(null);

  const [audioState, setAudioState] = useState<AudioState>("IDLE");
  const [audioError, setAudioError] = useState<string>("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cachedAudioBase64Ref = useRef<string | null>(null);

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
        return "Listening to your shop...";
      case "THINKING":
        return "Kavach is thinking...";
      case "INSIGHT_FOUND":
        return "Insight detected";
      case "REVIEW_ACTION":
        return "Reviewing action";
      case "APPROVING":
        return "Processing confirmation...";
      case "ACTION_PREPARED":
        return "Action prepared";
      case "REJECTED":
        return "Action declined";
      default:
        return "Kavach is ready";
    }
  };

  return (
    <div className="app">
      {/* Background Glows */}
      <div className="glow glow-top" />
      <div className="glow glow-bottom" />

      {/* Header */}
      <header className="topbar">
        <div className="brand" onClick={resetFlow} style={{ cursor: "pointer" }}>
          <div className="brand-icon">
            <ShieldCheck size={18} />
          </div>
          <div>
            <h1>Kirana Kavach</h1>
            <p>Sharma General Store · Mumbai</p>
          </div>
        </div>

        <div className="status-pill">
          <span
            className={`status-dot ${copilotState === "LISTENING"
                ? "listening"
                : copilotState === "THINKING" || copilotState === "APPROVING"
                  ? "thinking"
                  : copilotState === "ACTION_PREPARED"
                    ? "success"
                    : ""
              }`}
          />
          {renderStatusText()}
        </div>
      </header>

      {/* Spoken Pill (When active in insight or review screens) */}
      {(copilotState === "INSIGHT_FOUND" ||
        copilotState === "REVIEW_ACTION" ||
        copilotState === "APPROVING" ||
        copilotState === "ACTION_PREPARED" ||
        copilotState === "REJECTED") && (
          <div className="spoken-pill-container">
            <div className="spoken-pill">
              "{transcript || voiceData?.spoken_text || "मेरी दुकान पे ग्राहक कम आ रहे हैं"}"
            </div>
          </div>
        )}

      {/* Main Container */}
      <main className="main-content">
        {/* Error Notification */}
        {error && (
          <div className="error-banner">
            <AlertCircle size={18} />
            <div>
              <span>Error</span>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* ================================================= */}
        {/* 1. IDLE / LISTENING / THINKING HERO AREA         */}
        {/* ================================================= */}
        {(copilotState === "IDLE" ||
          copilotState === "LISTENING" ||
          copilotState === "THINKING") && (
            <div className="hero-section">
              <div className="hero-titles">
                <h2>Your shop speaks.</h2>
                <h2 className="lavender">Kavach listens.</h2>
              </div>

              <p className="hero-subtitle">
                Speak naturally about your business. Kavach finds what needs
                attention and helps you take the next step.
              </p>

              {/* Central Circular Orb Interaction */}
              <div className="orb-wrapper">
                {copilotState === "LISTENING" && (
                  <>
                    <div className="pulse-ring ring-1" />
                    <div className="pulse-ring ring-2" />
                    <div className="pulse-ring ring-3" />
                  </>
                )}

                <button
                  className={`main-orb ${copilotState === "LISTENING"
                      ? "orb-listening"
                      : copilotState === "THINKING"
                        ? "orb-thinking"
                        : "orb-idle"
                    }`}
                  onClick={handleVoice}
                  disabled={copilotState === "THINKING"}
                  aria-label="Talk to Kavach"
                >
                  {copilotState === "THINKING" ? (
                    <Sparkles size={38} className="spin-pulse" />
                  ) : copilotState === "LISTENING" ? (
                    <div className="equalizer-bars">
                      <span className="eq-bar bar-1" />
                      <span className="eq-bar bar-2" />
                      <span className="eq-bar bar-3" />
                      <span className="eq-bar bar-4" />
                      <span className="eq-bar bar-5" />
                    </div>
                  ) : (
                    <Mic size={38} />
                  )}
                </button>

                <div className="orb-labels">
                  <h3>
                    {copilotState === "THINKING"
                      ? "Kavach is thinking..."
                      : copilotState === "LISTENING"
                        ? "Listening..."
                        : "Talk to Kavach"}
                  </h3>
                  <p>
                    {copilotState === "THINKING"
                      ? "Analyzing your request & checking memory context"
                      : copilotState === "LISTENING"
                        ? transcript
                          ? `"${transcript}"`
                          : "Listening to your shop voice..."
                        : "Tap and tell me what's happening"}
                  </p>
                </div>
              </div>

              {/* Two Compact Context Cards (Idle state) */}
              {copilotState === "IDLE" && (
                <div className="context-cards-grid">
                  <div className="context-card try-card" onClick={handleVoice}>
                    <span className="card-tag">TRY SAYING</span>
                    <p className="hindi-prompt">"मेरी दुकान पे ग्राहक कम आ रहे हैं"</p>
                    <p className="english-sub">
                      "Fewer customers are coming to my shop" <ArrowRight size={13} style={{ display: "inline" }} />
                    </p>
                  </div>

                  <div className="context-card status-card">
                    <span className="card-tag">TODAY</span>
                    <p className="store-name">Sharma General Store</p>
                    <div className="activity-row">
                      <span>Customer activity</span>
                      <span className="badge-attention">● Needs attention</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

        {/* ================================================= */}
        {/* 2. INSIGHT CARD                                   */}
        {/* ================================================= */}
        {voiceData && copilotState === "INSIGHT_FOUND" && (
          <section className="insight-container">
            <div className="card-header-tag">
              <Sparkles size={14} />
              <span>KAVACH FOUND SOMETHING</span>
            </div>

            <h3 className="insight-title">
              {voiceData.reasoning.explanation ||
                "Regular customer visits have dropped significantly from their usual frequency."}
            </h3>

            {/* Metrics comparative box */}
            <div className="leak-metrics-box">
              <div className="metric-col">
                <span className="metric-label">Usually</span>
                <span className="metric-val text-white">Every ~2.6 days</span>
              </div>
              <span className="arrow-sep">→</span>
              <div className="metric-col">
                <span className="metric-label">Now</span>
                <span className="metric-val text-gold">~8.8 days</span>
              </div>

              <div className="comparison-bar">
                <div className="bar-fill" />
              </div>
            </div>

            <div className="rec-section">
              <span className="rec-label">RECOMMENDED ACTION</span>
              <p className="rec-text">{voiceData.reasoning.recommendation}</p>
            </div>

            <div className="insight-actions">
              <button
                className={`btn-audio-listen ${audioState === "PLAYING" ? "speaking" : ""
                  }`}
                onClick={handlePlayAudio}
                disabled={audioState === "PREPARING"}
              >
                {audioState === "PREPARING" ? (
                  <>
                    <Loader2 size={16} className="spin" />
                    <span>Preparing audio</span>
                  </>
                ) : audioState === "PLAYING" ? (
                  <>
                    <div className="equalizer-mini">
                      <span className="m-bar mb-1" />
                      <span className="m-bar mb-2" />
                      <span className="m-bar mb-3" />
                    </div>
                    <span>Speaking</span>
                  </>
                ) : audioState === "FINISHED" ? (
                  <>
                    <Volume2 size={16} />
                    <span>Listen again</span>
                  </>
                ) : audioState === "ERROR" ? (
                  <>
                    <VolumeX size={16} />
                    <span>{audioError || "Try again"}</span>
                  </>
                ) : (
                  <>
                    <Volume2 size={16} />
                    <span>Listen to Kavach</span>
                  </>
                )}
              </button>

              <button
                className="btn-review-primary"
                onClick={() => setCopilotState("REVIEW_ACTION")}
              >
                Review action
                <ArrowRight size={16} />
              </button>
            </div>
          </section>
        )}

        {/* ================================================= */}
        {/* 3. REVIEW ACTION PANEL                            */}
        {/* ================================================= */}
        {voiceData &&
          (copilotState === "REVIEW_ACTION" || copilotState === "APPROVING") && (
            <section className="review-container">
              <div className="card-header-tag">
                <FileText size={14} />
                <span>REVIEW BEFORE I ACT</span>
              </div>

              <div className="customer-row">
                <span className="meta-label">Customer</span>
                <span className="meta-val">
                  <User size={14} style={{ marginRight: 6, display: "inline" }} />
                  {voiceData.reasoning.action.payload.customer_id || "C1001"}
                </span>
              </div>

              {voiceData.reasoning.action.payload.message && (
                <div className="draft-message-section">
                  <span className="meta-label">Suggested message</span>
                  <div className="hindi-message-box">
                    <MessageSquare size={16} className="msg-icon" />
                    <p>"{voiceData.reasoning.action.payload.message}"</p>
                  </div>
                </div>
              )}

              <div className="chips-row">
                <span className="chip">Customer reactivation</span>
                <span className="chip">Merchant review</span>
                <span className="chip">Demo payment link</span>
              </div>

              <div className="disclaimer-pill">
                <ShieldCheck size={16} />
                <span>
                  Nothing is sent automatically. Review and approve the action first.
                </span>
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
                      <Loader2 size={16} className="spin" />
                      <span>Preparing...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} />
                      <span>Approve action</span>
                    </>
                  )}
                </button>
              </div>
            </section>
          )}

        {/* ================================================= */}
        {/* 4. ACTION PREPARED SUCCESS CARD                   */}
        {/* ================================================= */}
        {copilotState === "ACTION_PREPARED" && executionResult && (
          <section className="success-container">
            <div className="success-badge">
              <CheckCircle2 size={16} />
              <span>ACTION PREPARED</span>
            </div>

            <h3 className="success-title">Customer reactivation pack prepared</h3>
            <p className="success-sub">Prepared for merchant review.</p>

            <div className="meta-table">
              <div className="table-row">
                <span>Customer</span>
                <strong>{executionResult.customer_id || "C1001"}</strong>
              </div>
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
                <strong>{executionResult.provider || "n8n"}</strong>
              </div>
              <div className="table-row">
                <span>Reference</span>
                <strong className="mono">{executionResult.external_id || "KK-REACT-DEMO"}</strong>
              </div>
            </div>

            <div className="disclaimer-pill">
              <ShieldCheck size={16} />
              <span>Nothing was sent automatically.</span>
            </div>

            <div className="memory-badge">
              🧠 Kavach remembered this outcome
            </div>

            <button className="btn-start-over" onClick={resetFlow}>
              Start over
            </button>
          </section>
        )}

        {/* ================================================= */}
        {/* 5. REJECTED CARD                                  */}
        {/* ================================================= */}
        {copilotState === "REJECTED" && (
          <section className="rejected-container">
            <div className="rejected-icon">
              <Clock size={24} />
            </div>

            <h3>Okay. I won't take this action.</h3>
            <p>I'll keep this in mind for next time.</p>

            <button className="btn-start-over" onClick={resetFlow}>
              Talk to Kavach again
            </button>
          </section>
        )}

        {/* Bottom Trust Badges */}
        <div className="footer-trust-bar">
          <div className="trust-items">
            <span>🧠 Remembers your business</span>
            <span>🔒 You approve every action</span>
          </div>

          <div className="step-dots">
            <span
              className={`dot ${copilotState === "IDLE" ||
                  copilotState === "LISTENING" ||
                  copilotState === "THINKING"
                  ? "active"
                  : ""
                }`}
            />
            <span
              className={`dot ${copilotState === "INSIGHT_FOUND" ? "active" : ""
                }`}
            />
            <span
              className={`dot ${copilotState === "REVIEW_ACTION" || copilotState === "APPROVING"
                  ? "active"
                  : ""
                }`}
            />
            <span
              className={`dot ${copilotState === "ACTION_PREPARED" || copilotState === "REJECTED"
                  ? "active"
                  : ""
                }`}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;