# 🎬 YouTube AI Agent

A complete **multi-agent system** that autonomously generates YouTube-ready videos from a single topic input.

---

## 🏗️ Architecture

```
Topic Input ─► Research ─► Script ─► Voice ─► Visual ─► Editor
                                                            │
                                            Thumbnail ◄────┘
                                                │
                                           Metadata ─► QA ─► HITL ─► Finalizer ─► OUTPUT
```

### 9 Specialized Agents

| # | Agent | Role |
|---|-------|------|
| 1 | 🔍 Research | DuckDuckGo search + LLM analysis → key points, hooks, trends |
| 2 | ✍️ Script Writer | Hook + Intro + 4-5 sections + CTA in any language |
| 3 | 🎙️ Voice | edge-tts (free) neural voiceover per section |
| 4 | 🎨 Visual | PIL motion-graphics scenes + optional Stable Diffusion |
| 5 | 🎞️ Editor | Ken Burns zoom + cross-fade + subtitles + music → MP4 |
| 6 | 🖼️ Thumbnail | YouTube-style eye-catching thumbnail |
| 7 | 🧾 Metadata | SEO title, description (200-300w), 20 tags |
| 8 | ✅ QA | Score 0-100, grade A-F, issue detection |
| 9 | 👤 HITL | Human approval before final render |

---

## ⚡ Quick Start

### 1. Install dependencies

```bash
cd youtube-agent
pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
# Edit .env — minimum required: GROQ_API_KEY
```

Get a **free** Groq API key at [console.groq.com](https://console.groq.com) (uses Llama 3).

### 3. Run — CLI

```bash
# Basic
python main.py "Future of AI Agents in 2026"

# With options
python main.py "Black Holes Explained" \
  --language Tamil \
  --style Educational \
  --audience students

# Fully automated (skip approval)
python main.py "Crypto 2026" --auto
```

### 4. Run — Web UI

```bash
# Terminal 1: API server
python app.py

# Terminal 2: Streamlit dashboard
streamlit run ui.py
# Open http://localhost:8501
```

---

## 📁 Project Structure

```
youtube-agent/
├── .env.example          # Configuration template
├── requirements.txt      # Python dependencies
├── config.py             # Central config + palette system
├── main.py               # CLI entry point
├── app.py                # FastAPI REST server
├── ui.py                 # Streamlit dashboard
│
├── agents/               # 9 specialized agents
│   ├── research.py       # Web search + LLM analysis
│   ├── script_writer.py  # YouTube script generation
│   ├── voice.py          # TTS audio per section
│   ├── visual.py         # Scene image generation
│   ├── editor.py         # Video assembly
│   ├── thumbnail.py      # Thumbnail creation
│   ├── metadata.py       # SEO metadata
│   ├── qa.py             # Quality assurance
│   ├── hitl.py           # Human-in-the-loop
│   └── finalizer.py      # Output packaging
│
├── graph/
│   ├── state.py          # LangGraph state schema
│   └── workflow.py       # Full pipeline graph
│
├── tools/
│   ├── llm_client.py     # Multi-provider LLM (Groq/Ollama/OpenAI)
│   ├── tts_client.py     # TTS (edge-tts / ElevenLabs)
│   ├── image_client.py   # Scene generation (PIL / HuggingFace)
│   ├── search_client.py  # DuckDuckGo search
│   └── video_tools.py    # MoviePy/imageio assembly
│
├── assets/
│   ├── fonts/            # Noto fonts (multilingual)
│   └── music/            # Background music (add .mp3 here)
│
└── outputs/              # Generated files
    ├── videos/           # Final MP4 files
    ├── audio/            # Per-section MP3 files
    ├── images/           # Scene images
    ├── thumbnails/       # Thumbnail JPEGs
    ├── scripts/          # Script JSON files
    └── metadata/         # SEO metadata JSON
```

---

## 🔧 Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | `groq` \| `ollama` \| `openai` |
| `GROQ_API_KEY` | — | Free at console.groq.com |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Or `mixtral-8x7b-32768` |
| `TTS_PROVIDER` | `edge_tts` | Free Microsoft Neural TTS |
| `IMAGE_PROVIDER` | `local` | `local` (PIL) \| `huggingface` |
| `HF_API_TOKEN` | — | Free at huggingface.co (for SD images) |
| `VIDEO_WIDTH` | `1280` | Output width |
| `VIDEO_HEIGHT` | `720` | Output height |
| `VIDEO_FPS` | `24` | Output framerate |

---

## 📤 Output Files

For each job, you get:

| File | Description |
|------|-------------|
| `outputs/videos/{job_id}.mp4` | Final YouTube-ready video (1280x720) |
| `outputs/thumbnails/{job_id}.jpg` | Eye-catching thumbnail |
| `outputs/scripts/{job_id}.json` | Full script JSON |
| `outputs/metadata/{job_id}.json` | Title, description, tags |
| `outputs/{job_id}_summary.json` | Complete job summary |

---

## 🌍 Multilingual Support

Supports 11 languages via Microsoft Neural TTS:
English • Tamil • Hindi • Telugu • Spanish • French • German • Arabic • Japanese • Chinese • Portuguese

---

## 🎵 Background Music

Add royalty-free MP3 files to `assets/music/` — the editor will automatically mix them at 8% volume under the voiceover.

Free sources: [pixabay.com/music](https://pixabay.com/music), [freemusicarchive.org](https://freemusicarchive.org)

---

## 🚀 Deployment

### Render.com (free)

```yaml
# render.yaml
services:
  - type: web
    name: youtube-agent
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: GROQ_API_KEY
        sync: false
      - key: PORT
        value: 8000
```

---

## 📌 Example Run

```
$ python main.py "Future of AI Agents in 2026"

╔══════════════════════════════════════════════════════╗
║          🎬  YouTube AI Agent  v1.0                 ║
║   Research → Script → Voice → Visual → Edit → Done  ║
╚══════════════════════════════════════════════════════╝

📌 Topic:    Future of AI Agents in 2026
🌍 Language: English
🎭 Style:    Educational

[Research] Starting research...
[Research] Found 6 key points.
[Script] Writing script...
[Script] Generated 7 sections.
[Voice] Generating voiceover...
[Voice] Total duration: 342.5s (5.7 min)
[Visual] Generating scene images...
[Visual] Scene 7/7 rendered.
[Editor] Rendering 7 scenes, 8220 frames @ 24fps
[Editor] Done → outputs/videos/a3b2c1d0.mp4
[Thumbnail] Saved: outputs/thumbnails/a3b2c1d0.jpg
[Metadata] Saved: outputs/metadata/a3b2c1d0.json
[QA] Score: 88/100 — Grade: B

✅ Status: DONE
⏱️  Time:   187s (3.1 min)
📌 Title: AI Agents Will Replace 40% of Jobs by 2026 — Here's Why
🎬 Video:  outputs/videos/a3b2c1d0.mp4  (24.3MB)
```
