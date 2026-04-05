"""
Streamlit Dashboard — full UI for the YouTube AI Agent.
Run: streamlit run ui.py
"""
import streamlit as st
import json, time, os, requests
from pathlib import Path

API_BASE = os.getenv("API_URL", "https://youtube-agent-r838.onrender.com")

st.set_page_config(
    page_title="🎬 YouTube AI Agent",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .main { background: #0D0D1A; }
  .stApp { background: #0D0D1A; color: #E0E8FF; }
  h1, h2, h3 { color: #00C9FF; }
  .stButton > button {
    background: linear-gradient(90deg, #00C9FF, #92FE9D);
    color: #0D0D1A; font-weight: 800; border: none; border-radius: 10px;
    padding: 12px 28px; font-size: 1rem; cursor: pointer;
  }
  .stButton > button:hover { opacity: 0.88; transform: translateY(-1px); }
  .metric-card {
    background: #1A1A2E; border: 1px solid #00C9FF33;
    border-radius: 12px; padding: 16px; text-align: center;
  }
  .status-running { color: #92FE9D; }
  .status-done    { color: #00C9FF; }
  .status-failed  { color: #FF6B6B; }
  .agent-badge {
    display: inline-block; background: #00C9FF22;
    border: 1px solid #00C9FF44; border-radius: 20px;
    padding: 4px 14px; font-size: 0.78rem; color: #00C9FF;
    margin: 3px;
  }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎬 YouTube AI Agent")
    st.markdown("---")
    st.markdown("**Pipeline stages:**")
    for agent in ["🔍 Research", "✍️ Script Writer", "🎙️ Voice",
                  "🎨 Visual", "🎞️ Editor", "🖼️ Thumbnail",
                  "🧾 Metadata", "✅ QA", "👤 HITL", "📦 Finalizer"]:
        st.markdown(f"- {agent}")
    st.markdown("---")
    st.markdown("**Tech stack:**")
    st.markdown("- LangGraph orchestration")
    st.markdown("- Groq / Ollama LLM")
    st.markdown("- edge-tts voiceover")
    st.markdown("- PIL motion graphics")
    st.markdown("- FFmpeg video assembly")

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("🎬 YouTube AI Video Generator")
st.markdown("*Multi-agent pipeline: Research → Script → Voice → Visuals → Edit → Upload-ready*")

tab_gen, tab_status, tab_about = st.tabs(["🚀 Generate", "📊 Status", "ℹ️ About"])

# ── Generate Tab ──────────────────────────────────────────────────────────────
with tab_gen:
    col1, col2 = st.columns([2, 1])

    with col1:
        topic = st.text_input("🎯 Video Topic",
                              placeholder="e.g. Future of AI Agents in 2026",
                              help="Enter your YouTube video topic")

    with col2:
        language = st.selectbox("🌍 Language",
            ["English", "Tamil", "Hindi", "Telugu", "Spanish",
             "French", "German", "Arabic", "Japanese", "Chinese", "Portuguese"])

    col3, col4 = st.columns(2)
    with col3:
        style = st.selectbox("🎭 Style",
            ["Educational", "Cinematic", "Motivational", "Documentary", "Storytelling"])
    with col4:
        audience = st.selectbox("👥 Audience",
            ["general", "students", "professionals", "entrepreneurs", "tech enthusiasts"])

    st.markdown("---")

    if st.button("▶  Generate YouTube Video", use_container_width=True):
        if not topic.strip():
            st.error("⚠️ Please enter a topic.")
        else:
            # Start job via API
            try:
                r = requests.post(f"{API_BASE}/generate", json={
                    "topic": topic, "language": language,
                    "style": style, "audience": audience
                }, timeout=10)
                if r.status_code == 200:
                    job_id = r.json()["job_id"]
                    st.session_state["job_id"] = job_id
                    st.success(f"✅ Job started! ID: `{job_id}`")
                    st.info("Switch to the **📊 Status** tab to monitor progress.")
                else:
                    st.error(f"API error: {r.text}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to API. Make sure the server is running:\n```\npython app.py\n```")

    # Quick info
    st.markdown("---")
    st.markdown("### 🧠 What gets generated:")
    c1, c2, c3, c4 = st.columns(4)
    for col, emoji, label in [
        (c1, "📝", "Full Script"),
        (c2, "🎙️", "Voiceover MP3"),
        (c3, "🎬", "HD Video MP4"),
        (c4, "🖼️", "Thumbnail"),
    ]:
        col.markdown(f"""<div class="metric-card">{emoji}<br><b>{label}</b></div>""",
                     unsafe_allow_html=True)

# ── Status Tab ────────────────────────────────────────────────────────────────
with tab_status:
    job_id_input = st.text_input(
        "Job ID", value=st.session_state.get("job_id", ""),
        placeholder="Enter job ID or start a new job"
    )
    auto_refresh = st.toggle("Auto-refresh (every 3s)", value=True)

    if job_id_input:
        try:
            r = requests.get(f"{API_BASE}/status/{job_id_input}", timeout=5)
            if r.status_code == 200:
                job = r.json()
                status = job.get("status", "unknown")

                # Status badge
                color = {"done": "🟢", "running": "🔵",
                         "failed": "🔴", "queued": "🟡",
                         "waiting_approval": "🟠"}.get(status, "⚪")
                st.markdown(f"### {color} Status: `{status.upper()}`")

                # Progress metrics
                m1, m2, m3 = st.columns(3)
                dur = job.get("total_duration", 0)
                m1.metric("Duration", f"{int(dur//60)}:{int(dur%60):02d}")
                m2.metric("QA Score", f"{job.get('qa_report', {}).get('score', '--')}/100")
                m3.metric("Topic", job.get("topic", "")[:30])

                # Title
                if job.get("metadata", {}).get("title"):
                    st.markdown(f"**📌 Title:** {job['metadata']['title']}")

                # HITL Approval
                if status == "waiting_approval":
                    st.warning("⏳ Waiting for your approval before final render.")
                    qa = job.get("qa_report", {})
                    st.markdown(f"**QA Grade:** {qa.get('grade','?')} | "
                                f"**Score:** {qa.get('score',0)}/100")
                    if qa.get("issues"):
                        with st.expander("QA Issues"):
                            for issue in qa["issues"]:
                                st.write(f"- {issue}")
                    col_a, col_b = st.columns(2)
                    if col_a.button("✅ Approve & Finalize"):
                        ra = requests.post(f"{API_BASE}/approve/{job_id_input}",
                                           json={"approved": True})
                        st.success("Approved! Finalizing video...")
                        st.rerun()
                    if col_b.button("❌ Reject"):
                        requests.post(f"{API_BASE}/approve/{job_id_input}",
                                      json={"approved": False})
                        st.warning("Job rejected.")

                # Downloads
                if status == "done":
                    st.success("🎉 Video generation complete!")
                    d1, d2, d3, d4 = st.columns(4)
                    if job.get("video_ready"):
                        d1.markdown(f"[⬇️ Download Video]({API_BASE}/download/{job_id_input}/video)")
                    if job.get("thumbnail_ready"):
                        d2.markdown(f"[🖼️ Thumbnail]({API_BASE}/download/{job_id_input}/thumbnail)")
                    d3.markdown(f"[📝 Script]({API_BASE}/download/{job_id_input}/script)")
                    d4.markdown(f"[🏷️ Metadata]({API_BASE}/download/{job_id_input}/metadata)")

                    # Show metadata
                    meta = job.get("metadata", {})
                    if meta:
                        with st.expander("📋 Generated Metadata"):
                            st.markdown(f"**Title:** {meta.get('title','')}")
                            st.markdown(f"**Tags:** {', '.join(meta.get('tags',[])[:10])}")
                            if meta.get("description"):
                                st.text_area("Description", meta["description"], height=200)

                # Logs
                logs = job.get("logs", [])
                if logs:
                    with st.expander(f"📜 Logs ({len(logs)} entries)", expanded=(status == "running")):
                        for log in logs[-30:]:
                            if "[Error]" in log or "Error" in log:
                                st.markdown(f":red[{log}]")
                            elif "✓" in log or "Done" in log or "Saved" in log:
                                st.markdown(f":green[{log}]")
                            else:
                                st.write(log)

                # Errors
                if job.get("errors"):
                    with st.expander("🚨 Errors"):
                        for err in job["errors"]:
                            st.error(err)

                # Auto-refresh
                if auto_refresh and status in ("running", "queued", "finalizing"):
                    time.sleep(3)
                    st.rerun()

            elif r.status_code == 404:
                st.warning("Job not found. Check the job ID.")
            else:
                st.error(f"Error: {r.text}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to API server.")
        except Exception as e:
            st.error(f"Error: {e}")

# ── About Tab ─────────────────────────────────────────────────────────────────
with tab_about:
    st.markdown("""
## 🏗️ Architecture

```
Topic Input
    │
    ▼
┌─────────────────────────────────────────────────┐
│              LangGraph Orchestrator              │
│                                                  │
│  1. 🔍 Research Agent                            │
│     └── DuckDuckGo search + LLM analysis        │
│                                                  │
│  2. ✍️ Script Writer Agent                       │
│     └── Hook + Intro + 4-5 Sections + CTA       │
│                                                  │
│  3. 🎙️ Voice Agent                               │
│     └── edge-tts / ElevenLabs per section        │
│                                                  │
│  4. 🎨 Visual Agent                              │
│     └── PIL motion-graphics / HuggingFace SD    │
│                                                  │
│  5. 🎞️ Editor Agent                              │
│     └── Ken Burns + subtitles + transitions      │
│                                                  │
│  6. 🖼️ Thumbnail Agent                           │
│     └── Eye-catching PIL thumbnail              │
│                                                  │
│  7. 🧾 Metadata Agent                            │
│     └── SEO title + description + tags          │
│                                                  │
│  8. ✅ QA Agent                                  │
│     └── Score 0-100, grade A-F                   │
│                                                  │
│  9. 👤 HITL Agent                                │
│     └── Human approval before final render      │
│                                                  │
│ 10. 📦 Finalizer                                  │
│     └── Package + save all outputs              │
└─────────────────────────────────────────────────┘
    │
    ▼
  MP4 + Thumbnail + Script + Metadata JSON
```

## ⚙️ Setup

```bash
cd youtube-agent
cp .env.example .env
# Edit .env with your GROQ_API_KEY (free at console.groq.com)
pip install -r requirements.txt

# Terminal 1 — API server
python app.py

# Terminal 2 — UI
streamlit run ui.py
```

## 💡 CLI Usage

```bash
python main.py "Future of AI Agents in 2026"
python main.py "Black Holes Explained" --language Tamil --style Educational
```
    """)
