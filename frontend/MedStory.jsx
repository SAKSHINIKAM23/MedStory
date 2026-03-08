import { useState, useRef, useEffect } from "react";

const API_BASE = import.meta.env?.VITE_API_BASE || "http://localhost:8080";

const SUGGESTIONS = [
  "Appendectomy","Knee Replacement","Cataract Surgery",
  "Colonoscopy","Hip Replacement","LASIK Eye Surgery",
  "Tonsillectomy","Gallbladder Removal","MRI Scan",
];

const STEPS = [
  { id:1, label:"Script",    icon:"✍️", desc:"Writing patient-friendly content" },
  { id:2, label:"Diagrams",  icon:"🫀", desc:"Generating medical illustrations" },
  { id:3, label:"Narration", icon:"🎙️", desc:"Synthesizing voice narration" },
  { id:4, label:"Video",     icon:"🎬", desc:"Assembling final video" },
];

function getActiveStep(progress) {
  if (progress < 30) return 1;
  if (progress < 60) return 2;
  if (progress < 85) return 3;
  return 4;
}

export default function MedStory() {
  const [procedure, setProcedure] = useState("");
  const [showSugg,  setShowSugg]  = useState(false);
  const [phase,     setPhase]     = useState("input");
  const [job,       setJob]       = useState(null);
  const [activeScene, setActiveScene] = useState(0);
  const [mounted,   setMounted]   = useState(false);
  const pollRef = useRef(null);

  useEffect(() => { setMounted(true); }, []);

  const filtered = SUGGESTIONS.filter(s =>
    s.toLowerCase().includes(procedure.toLowerCase()) && procedure.length > 0
  );

  async function handleGenerate() {
    if (!procedure.trim()) return;
    setPhase("loading");
    setJob({ status:"queued", progress:0, current_step:"Initialising pipeline..." });

    const res = await fetch(`${API_BASE}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ procedure }),
    });
    const data = await res.json();
    const jobId = data.job_id;

    pollRef.current = setInterval(async () => {
      const r = await fetch(`${API_BASE}/jobs/${jobId}`);
      const j = await r.json();
      setJob(j);
      if (j.status === "complete" || j.status === "error") {
        clearInterval(pollRef.current);
        if (j.status === "complete") setPhase("result");
      }
    }, 5000);
  }

  function reset() {
    clearInterval(pollRef.current);
    setPhase("input"); setProcedure(""); setJob(null); setActiveScene(0);
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "#f7f5f0",
      color: "#1a1a2e",
      fontFamily: "'Instrument Sans', sans-serif",
      position: "relative",
      overflow: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Instrument+Serif:ital@0;1&display=swap');

        * { box-sizing: border-box; }

        :root {
          --teal: #0d7377;
          --teal-light: #14a085;
          --teal-pale: #e8f5f4;
          --cream: #f7f5f0;
          --cream-dark: #ede9e0;
          --ink: #1a1a2e;
          --ink-muted: #6b6b7d;
          --ink-subtle: #a8a8b8;
          --gold: #c8972a;
          --red-soft: #e05c5c;
        }

        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(28px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; } to { opacity: 1; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes pulse-ring {
          0%   { transform: scale(1);   opacity: .6; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        @keyframes barFill {
          from { width: 0%; } to { width: var(--bar-w); }
        }
        @keyframes stepPop {
          0%   { transform: scale(.92); opacity: 0; }
          60%  { transform: scale(1.04); }
          100% { transform: scale(1);   opacity: 1; }
        }

        .fade-up { animation: fadeUp .55s cubic-bezier(.22,.68,0,1.2) both; }
        .fade-up-2 { animation: fadeUp .55s .12s cubic-bezier(.22,.68,0,1.2) both; }
        .fade-up-3 { animation: fadeUp .55s .24s cubic-bezier(.22,.68,0,1.2) both; }

        .pill-tag {
          display: inline-flex; align-items: center; gap: 6px;
          padding: 5px 13px; border-radius: 99px;
          border: 1px solid var(--cream-dark);
          background: white; font-size: 12px; color: var(--ink-muted);
          font-weight: 500; letter-spacing: .01em;
          transition: border-color .2s, color .2s;
        }

        .generate-btn {
          background: var(--teal);
          border: none; border-radius: 10px;
          padding: 13px 28px; color: white;
          font-size: 14px; font-weight: 600;
          cursor: pointer; font-family: inherit;
          letter-spacing: .02em;
          transition: background .2s, transform .15s, box-shadow .2s;
          box-shadow: 0 4px 16px rgba(13,115,119,.25);
          white-space: nowrap;
        }
        .generate-btn:hover:not(:disabled) {
          background: var(--teal-light);
          transform: translateY(-1px);
          box-shadow: 0 8px 28px rgba(13,115,119,.35);
        }
        .generate-btn:disabled {
          background: var(--ink-subtle); box-shadow: none; cursor: default;
        }

        .scene-card {
          background: white; border: 1.5px solid var(--cream-dark);
          border-radius: 14px; padding: 18px; cursor: pointer;
          transition: border-color .2s, transform .2s, box-shadow .2s;
        }
        .scene-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.07); border-color: var(--teal); }
        .scene-card.active { border-color: var(--teal); background: var(--teal-pale); }

        .sugg-item {
          padding: 11px 18px; cursor: pointer; font-size: 14px;
          color: var(--ink); transition: background .15s;
          display: flex; align-items: center; gap: 9px;
          border-bottom: 1px solid #f0ede7;
        }
        .sugg-item:hover { background: var(--teal-pale); }
        .sugg-item:last-child { border-bottom: none; }

        .pill-wrapper {
          position: relative; display: inline-flex;
        }
        .pill-wrapper .tooltip {
          visibility: hidden; opacity: 0;
          position: absolute; bottom: calc(100% + 10px); left: 50%;
          transform: translateX(-50%) translateY(4px);
          background: #1a1a2e; color: white;
          font-size: 12px; line-height: 1.5;
          padding: 8px 12px; border-radius: 9px;
          white-space: nowrap; pointer-events: none;
          box-shadow: 0 8px 24px rgba(0,0,0,.2);
          transition: opacity .18s ease, transform .18s ease;
          z-index: 100;
        }
        .pill-wrapper .tooltip::after {
          content: '';
          position: absolute; top: 100%; left: 50%;
          transform: translateX(-50%);
          border: 6px solid transparent;
          border-top-color: #1a1a2e;
        }
        .pill-wrapper:hover .tooltip {
          visibility: visible; opacity: 1;
          transform: translateX(-50%) translateY(0);
        }

        .step-card {
          border-radius: 14px; padding: 20px 14px; text-align: center;
          border: 1.5px solid var(--cream-dark); background: white;
          transition: all .4s cubic-bezier(.22,.68,0,1.2);
        }
        .step-card.current {
          border-color: var(--teal);
          background: var(--teal-pale);
          box-shadow: 0 4px 20px rgba(13,115,119,.12);
          animation: stepPop .4s ease both;
        }
        .step-card.done {
          border-color: #b8e0d9;
          background: #f0faf8;
        }

        .back-btn {
          padding: 9px 20px; border-radius: 9px;
          background: white; border: 1.5px solid var(--cream-dark);
          color: var(--ink-muted); cursor: pointer; font-size: 13px;
          font-family: inherit; font-weight: 500;
          transition: border-color .2s, color .2s;
        }
        .back-btn:hover { border-color: var(--teal); color: var(--teal); }

        /* Decorative SVG pattern */
        .bg-pattern {
          position: fixed; inset: 0; pointer-events: none; z-index: 0; opacity: .45;
          background-image: radial-gradient(circle, #0d737720 1px, transparent 1px);
          background-size: 36px 36px;
        }
        .bg-blob {
          position: fixed; pointer-events: none; z-index: 0; border-radius: 50%;
          filter: blur(90px); opacity: .25;
        }
      `}</style>

      {/* Background atmosphere */}
      <div className="bg-pattern" />
      <div className="bg-blob" style={{ width:560, height:560, background:"#0d7377", top:-200, right:-150 }} />
      <div className="bg-blob" style={{ width:400, height:400, background:"#c8972a", bottom:-100, left:-100 }} />

      {/* Header */}
      <header style={{
        position: "relative", zIndex: 10,
        padding: "18px 48px",
        borderBottom: "1px solid #e8e4da",
        background: "rgba(247,245,240,.85)",
        backdropFilter: "blur(12px)",
        display: "flex", alignItems: "center", gap: 14,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12,
          background: "var(--teal)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 19, boxShadow: "0 4px 14px rgba(13,115,119,.3)",
        }}>🩺</div>
        <div>
          <div style={{ fontSize: 17, fontWeight: 700, fontFamily: "'Instrument Serif', serif", letterSpacing: "-.01em" }}>
            MedStory
          </div>
          <div style={{ fontSize: 10.5, color: "var(--ink-subtle)", textTransform: "uppercase", letterSpacing: ".1em", fontWeight: 500 }}>
            Patient Education AI
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 7,
          padding: "5px 14px", borderRadius: 99,
          background: "white", border: "1px solid #d5f0ec",
          fontSize: 12, color: "var(--teal)", fontWeight: 600,
        }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--teal)", display: "inline-block" }} />
          Vertex AI · Gemini
        </div>
      </header>

      <main style={{ position: "relative", zIndex: 5, maxWidth: 900, margin: "0 auto", padding: "60px 28px" }}>

        {/* ───── INPUT ───── */}
        {phase === "input" && (
          <div>
            <div className="fade-up" style={{ textAlign: "center", marginBottom: 52 }}>
              <div style={{
                display: "inline-block", padding: "5px 16px",
                borderRadius: 99, background: "white", border: "1px solid #d5f0ec",
                fontSize: 12, color: "var(--teal)", fontWeight: 600,
                letterSpacing: ".04em", textTransform: "uppercase", marginBottom: 20,
              }}>
                AI-Powered Patient Education
              </div>
              <h1 style={{
                fontSize: "clamp(32px,5vw,56px)", fontWeight: 700,
                fontFamily: "'Instrument Serif', serif",
                color: "var(--ink)", margin: "0 0 6px",
                letterSpacing: "-.025em", lineHeight: 1.12,
              }}>
                Turn procedures into<br />
                <em style={{ color: "var(--teal)", fontStyle: "italic" }}>clear patient videos</em>
              </h1>
              <p style={{ color: "var(--ink-muted)", fontSize: 16, marginTop: 16, lineHeight: 1.6 }}>
                Enter any medical procedure — AI writes the script, generates<br />
                diagrams, records narration, and assembles a patient-ready video.
              </p>
            </div>

            {/* Search box */}
            <div className="fade-up-2" style={{ position: "relative", maxWidth: 640, margin: "0 auto 44px" }}>
              <div style={{
                background: "white",
                border: "1.5px solid var(--cream-dark)",
                borderRadius: 16, display: "flex", alignItems: "center",
                padding: "5px 5px 5px 20px", gap: 12,
                boxShadow: "0 4px 32px rgba(0,0,0,.07)",
                transition: "border-color .2s, box-shadow .2s",
              }}
              onFocus={() => {}} >
                <span style={{ fontSize: 17, lineHeight: 1 }}>🔬</span>
                <input
                  value={procedure}
                  onChange={e => { setProcedure(e.target.value); setShowSugg(true); }}
                  onFocus={() => setShowSugg(true)}
                  onBlur={() => setTimeout(() => setShowSugg(false), 150)}
                  onKeyDown={e => e.key === "Enter" && handleGenerate()}
                  placeholder="Enter medical procedure (e.g. Appendectomy)"
                  style={{
                    flex: 1, background: "none", border: "none", outline: "none",
                    color: "var(--ink)", fontSize: 15.5, padding: "13px 0",
                    fontFamily: "inherit", fontWeight: 500,
                  }}
                />
                <button onClick={handleGenerate} disabled={!procedure.trim()} className="generate-btn">
                  Generate →
                </button>
              </div>

              {/* Suggestions */}
              {showSugg && filtered.length > 0 && (
                <div style={{
                  position: "absolute", top: "calc(100% + 8px)", left: 0, right: 0,
                  background: "white", border: "1.5px solid var(--cream-dark)",
                  borderRadius: 12, overflow: "hidden", zIndex: 50,
                  boxShadow: "0 12px 48px rgba(0,0,0,.1)",
                  animation: "fadeIn .15s ease",
                }}>
                  {filtered.map(s => (
                    <div
                      key={s}
                      className="sugg-item"
                      onMouseDown={e => { e.preventDefault(); setProcedure(s); setShowSugg(false); }}
                    >
                      <span style={{ color: "var(--teal)", fontSize: 13 }}>↗</span>
                      {s}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Feature pills */}
            <div className="fade-up-3" style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center" }}>
              {[
                ["✍️", "AI Script Writing",  "Gemini writes a 5-scene patient-friendly script at an 8th-grade reading level."],
                ["🫀", "Medical Diagrams",   "Imagen 3 generates a custom medical illustration for every scene."],
                ["🎙️", "Voice Narration",    "Google Text-to-Speech synthesizes natural-sounding audio for each scene."],
                ["🎬", "Video Assembly",     "FFmpeg stitches images and audio into a polished MP4 with smooth transitions."],
                ["🌐", "Plain Language",     "All content is written to be clear and reassuring — no medical jargon."],
                ["🔒", "Education Only",     "The AI is instructed never to give diagnoses or specific medical advice."],
              ].map(([icon, label, tip]) => (
                <div key={label} className="pill-wrapper">
                  <div className="pill-tag">{icon} {label}</div>
                  <div className="tooltip">{tip}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ───── LOADING ───── */}
        {phase === "loading" && (
          <div style={{ textAlign: "center", animation: "fadeUp .5s ease both" }}>
            {/* Pulse spinner */}
            <div style={{ position: "relative", width: 80, height: 80, margin: "0 auto 28px" }}>
              <div style={{
                position: "absolute", inset: 0, borderRadius: "50%",
                border: "2px solid var(--teal)", opacity: .4,
                animation: "pulse-ring 1.4s ease-out infinite",
              }} />
              <div style={{
                width: 80, height: 80, borderRadius: "50%",
                border: "2.5px solid var(--cream-dark)",
                borderTop: "2.5px solid var(--teal)",
                animation: "spin 1s linear infinite",
              }} />
            </div>

            <h2 style={{ fontSize: 26, fontWeight: 700, fontFamily: "'Instrument Serif', serif", marginBottom: 6, letterSpacing: "-.01em" }}>
              Building <em style={{ color: "var(--teal)" }}>{procedure}</em> explainer
            </h2>
            <p style={{ color: "var(--ink-muted)", marginBottom: 32, fontSize: 14 }}>
              {job?.progress < 20 ? "Generating script..." :
               job?.progress < 60 ? "Creating visuals and narration..." :
               job?.progress < 100 ? "Rendering video..." :
               "Finishing up..."}
            </p>

            {/* Progress bar */}
            <div style={{ maxWidth: 560, margin: "0 auto 36px", background: "var(--cream-dark)", borderRadius: 99, height: 6, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 99,
                background: "linear-gradient(90deg, var(--teal), var(--teal-light))",
                width: `${job?.progress || 3}%`,
                transition: "width .9s cubic-bezier(.22,.68,0,1.2)",
              }} />
            </div>

            {/* Step cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, maxWidth: 680, margin: "0 auto" }}>
              {STEPS.map(step => {
                const active = getActiveStep(job?.progress || 0);
                const done = step.id < active, current = step.id === active;
                return (
                  <div key={step.id} className={`step-card ${current ? "current" : done ? "done" : ""}`}>
                    <div style={{ fontSize: 26, marginBottom: 8 }}>{done ? "✅" : step.icon}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: current ? "var(--teal)" : done ? "#14a085" : "var(--ink-subtle)", marginBottom: 4 }}>
                      {step.label}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--ink-subtle)", lineHeight: 1.4 }}>{step.desc}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ───── RESULT ───── */}
        {phase === "result" && job?.result && (
          <div style={{ animation: "fadeUp .5s ease both" }}>
            {/* Header row */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 32, flexWrap: "wrap", gap: 14 }}>
              <div>
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "4px 13px", borderRadius: 99,
                  background: "#f0faf8", border: "1px solid #b8e0d9",
                  fontSize: 12, color: "var(--teal)", fontWeight: 600, marginBottom: 10,
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--teal)", display: "inline-block" }} />
                  Video Generated
                </div>
                <h2 style={{ fontSize: 30, fontWeight: 700, fontFamily: "'Instrument Serif', serif", margin: "0 0 6px", letterSpacing: "-.015em" }}>
                  {job.result.title}
                </h2>
                <p style={{ color: "var(--ink-muted)", fontSize: 14, lineHeight: 1.6, maxWidth: 540 }}>
                  {job.result.summary}
                </p>
              </div>
              <button onClick={reset} className="back-btn">← New Video</button>
            </div>

            {/* Video player */}
            <div style={{
              background: "#111", borderRadius: 18, overflow: "hidden",
              marginBottom: 24, aspectRatio: "16/9", position: "relative",
              border: "1.5px solid #2a2a2a",
              boxShadow: "0 20px 60px rgba(0,0,0,.18)",
            }}>
              {job.result.video_url ? (
                <video
                  key={job.result.video_url}
                  src={`${API_BASE}${job.result.video_url}`}
                  controls
                  autoPlay
                  playsInline
                  preload="auto"
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  onError={e => console.error("Video load error:", e)}
                />
              ) : job.result.scenes[activeScene]?.image_base64 ? (
                <img
                  src={`data:image/png;base64,${job.result.scenes[activeScene].image_base64}`}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  alt="scene"
                />
              ) : (
                <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 64 }}>
                  🎬
                </div>
              )}

              {/* Overlay caption */}
              <div style={{
                position: "absolute", bottom: 0, left: 0, right: 0,
                background: "linear-gradient(transparent, rgba(0,0,0,.82))",
                padding: "48px 24px 20px",
                pointerEvents: "none",
              }}>
                <div style={{ fontWeight: 700, fontSize: 17, color: "white", marginBottom: 5 }}>
                  {job.result.scenes[activeScene]?.title}
                </div>
                <div style={{ fontSize: 13, color: "rgba(255,255,255,.6)", lineHeight: 1.5 }}>
                  {job.result.scenes[activeScene]?.narration?.slice(0, 110)}…
                </div>
              </div>

              {/* Dot nav */}
              <div style={{ position: "absolute", bottom: 18, left: "50%", transform: "translateX(-50%)", display: "flex", gap: 6 }}>
                {job.result.scenes.map((_, i) => (
                  <button key={i} onClick={() => setActiveScene(i)} style={{
                    width: i === activeScene ? 24 : 7, height: 7, borderRadius: 99,
                    background: i === activeScene ? "var(--teal)" : "rgba(255,255,255,.3)",
                    border: "none", cursor: "pointer", padding: 0,
                    transition: "all .3s cubic-bezier(.22,.68,0,1.2)",
                  }} />
                ))}
              </div>

              {/* Download button - streams directly from server */}
              {job.result.video_url && (
                <a
                  href={`${API_BASE}${job.result.video_url}`}
                  download="medstory_explainer.mp4"
                  style={{
                    position: "absolute", top: 14, right: 14,
                    padding: "8px 16px", borderRadius: 9,
                    background: "rgba(255,255,255,.12)", backdropFilter: "blur(8px)",
                    border: "1px solid rgba(255,255,255,.2)",
                    color: "white", fontSize: 13, textDecoration: "none", fontWeight: 600,
                  }}
                >
                  ⬇ Download MP4
                </a>
              )}
            </div>

            {/* Scene cards */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 12, marginBottom: 18 }}>
              {job.result.scenes.map((scene, i) => (
                <div key={i} className={`scene-card ${i === activeScene ? "active" : ""}`} onClick={() => setActiveScene(i)}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: i === activeScene ? "var(--teal)" : "var(--cream-dark)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: 700,
                      color: i === activeScene ? "white" : "var(--ink-muted)",
                      flexShrink: 0,
                    }}>
                      {scene.scene_number}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", lineHeight: 1.3 }}>{scene.title}</div>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink-muted)", lineHeight: 1.65 }}>
                    {scene.narration.slice(0, 85)}…
                  </div>
                  <div style={{ display: "flex", gap: 5, marginTop: 10 }}>
                    {scene.image_base64 && (
                      <span style={{ fontSize: 11, color: "var(--teal)", background: "var(--teal-pale)", padding: "2px 8px", borderRadius: 5, fontWeight: 600 }}>
                        🖼 Image
                      </span>
                    )}
                    {scene.audio_base64 && (
                      <span style={{ fontSize: 11, color: "#7c5cbf", background: "#f4f0fa", padding: "2px 8px", borderRadius: 5, fontWeight: 600 }}>
                        🎙 Audio
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Disclaimer */}
            <div style={{
              padding: "13px 18px", borderRadius: 10,
              background: "#fffbf0", border: "1.5px solid #f0d88a",
              fontSize: 13, color: "#92680a", lineHeight: 1.6,
            }}>
              ⚠️ {job.result.disclaimer}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}