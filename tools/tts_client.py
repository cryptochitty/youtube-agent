"""TTS client — edge-tts primary, ElevenLabs optional."""
import asyncio, os, re, subprocess
from pathlib import Path
from config import TTS_PROVIDER, ELEVENLABS_KEY, VOICE_MAP


# ── edge-tts (Microsoft Neural, free) ────────────────────────────────────────
def generate_edge_tts(text: str, voice: str, out_path: str) -> float:
    """Generate audio file via edge-tts. Returns duration in seconds."""
    import edge_tts

    async def _run():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)

    asyncio.run(_run())
    return get_audio_duration(out_path)


# ── ElevenLabs (premium quality) ─────────────────────────────────────────────
def generate_elevenlabs(text: str, voice_id: str, out_path: str) -> float:
    import requests
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"}
    body = {"text": text, "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}
    r = requests.post(url, json=body, headers=headers)
    if r.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(r.content)
        return get_audio_duration(out_path)
    raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text}")


# ── Duration helper ───────────────────────────────────────────────────────────
def get_audio_duration(path: str) -> float:
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        r = subprocess.run([ffmpeg, '-i', path], capture_output=True, text=True)
        m = re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', r.stderr)
        if m:
            h, mn, s = m.groups()
            return int(h)*3600 + int(mn)*60 + float(s)
    except Exception:
        pass
    return 5.0


# ── Public API ────────────────────────────────────────────────────────────────
def synthesize(text: str, language: str, out_path: str) -> float:
    """Generate speech audio. Returns duration in seconds."""
    voice = VOICE_MAP.get(language, VOICE_MAP["English"])

    if TTS_PROVIDER == "elevenlabs" and ELEVENLABS_KEY:
        voice_ids = {
            "English": "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "default": "21m00Tcm4TlvDq8ikWAM",
        }
        vid = voice_ids.get(language, voice_ids["default"])
        return generate_elevenlabs(text, vid, out_path)

    # Default: edge-tts
    return generate_edge_tts(text, voice, out_path)


def concat_audios(audio_files: list, out_path: str):
    """Concatenate multiple audio files using ffmpeg."""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    list_file = out_path + ".list.txt"
    with open(list_file, "w") as f:
        for af in audio_files:
            f.write(f"file '{af}'\n")
    subprocess.run([ffmpeg, '-y', '-f', 'concat', '-safe', '0',
                    '-i', list_file, '-c', 'copy', out_path],
                   capture_output=True)
    try:
        os.remove(list_file)
    except Exception:
        pass
