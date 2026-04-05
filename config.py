"""Central configuration — reads from .env"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / "outputs"
ASSETS_DIR  = BASE_DIR / "assets"
FONTS_DIR   = ASSETS_DIR / "fonts"
MUSIC_DIR   = ASSETS_DIR / "music"

# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_PROVIDER  = os.getenv("LLM_PROVIDER", "groq")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OLLAMA_URL    = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL", "llama3.2")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── TTS ───────────────────────────────────────────────────────────────────────
TTS_PROVIDER      = os.getenv("TTS_PROVIDER", "edge_tts")
ELEVENLABS_KEY    = os.getenv("ELEVENLABS_API_KEY", "")

# ── Images ────────────────────────────────────────────────────────────────────
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "local")
HF_API_TOKEN   = os.getenv("HF_API_TOKEN", "")

# ── Video ─────────────────────────────────────────────────────────────────────
VIDEO_W   = int(os.getenv("VIDEO_WIDTH",  "640"))
VIDEO_H   = int(os.getenv("VIDEO_HEIGHT", "360"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS",    "8"))

# ── Voice map (language → edge-tts voice) ─────────────────────────────────────
VOICE_MAP = {
    "English":    "en-US-JennyNeural",
    "Tamil":      "ta-IN-PallaviNeural",
    "Hindi":      "hi-IN-SwaraNeural",
    "Telugu":     "te-IN-ShrutiNeural",
    "Spanish":    "es-ES-ElviraNeural",
    "French":     "fr-FR-DeniseNeural",
    "German":     "de-DE-KatjaNeural",
    "Arabic":     "ar-EG-SalmaNeural",
    "Japanese":   "ja-JP-NanamiNeural",
    "Chinese":    "zh-CN-XiaoxiaoNeural",
    "Portuguese": "pt-BR-FranciscaNeural",
}

# ── Scene color palettes (by topic mood) ──────────────────────────────────────
PALETTES = {
    "tech":        {"bg1": (5,5,25),    "bg2": (15,15,60),  "accent": (0,210,255),  "accent2": (120,60,255), "text": (230,240,255)},
    "science":     {"bg1": (3,12,30),   "bg2": (10,30,60),  "accent": (0,180,255),  "accent2": (0,255,180),  "text": (220,240,255)},
    "finance":     {"bg1": (8,12,8),    "bg2": (15,35,20),  "accent": (50,220,100), "accent2": (200,220,50), "text": (230,245,230)},
    "motivation":  {"bg1": (25,5,5),    "bg2": (60,15,10),  "accent": (255,120,30), "accent2": (255,60,100), "text": (255,240,230)},
    "education":   {"bg1": (5,10,30),   "bg2": (15,25,60),  "accent": (80,160,255), "accent2": (160,80,255), "text": (230,235,255)},
    "health":      {"bg1": (5,20,15),   "bg2": (10,45,30),  "accent": (60,220,140), "accent2": (60,200,220), "text": (225,245,235)},
    "default":     {"bg1": (8,8,22),    "bg2": (18,18,50),  "accent": (0,200,255),  "accent2": (150,100,255),"text": (235,235,255)},
}

def get_palette(topic: str) -> dict:
    topic_l = topic.lower()
    for kw, pal in [
        (["ai","tech","robot","software","code","digital","cyber","future"], "tech"),
        (["science","physics","chemistry","biology","space","quantum"],       "science"),
        (["money","finance","invest","crypto","stock","business"],            "finance"),
        (["motivat","success","mindset","habit","productiv","goal"],          "motivation"),
        (["learn","education","history","skill","course","study"],            "education"),
        (["health","fitness","diet","mental","wellness","yoga"],               "health"),
    ]:
        if any(k in topic_l for k in kw):
            return PALETTES[pal]
    return PALETTES["default"]

# Ensure output dirs exist
for _sub in ["scripts","audio","images","videos","thumbnails","metadata"]:
    (OUTPUTS_DIR / _sub).mkdir(parents=True, exist_ok=True)
