"""
Video assembly tools — combines images + audio into MP4 with
subtitles, zoom effects, transitions, and background music.
"""
import os, subprocess, textwrap, math
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio
from config import VIDEO_W, VIDEO_H, VIDEO_FPS, FONTS_DIR, MUSIC_DIR

W, H, FPS = VIDEO_W, VIDEO_H, VIDEO_FPS

# ── Font cache ────────────────────────────────────────────────────────────────
_FC = {}
def _font(size, bold=False):
    k = (size, bold)
    if k not in _FC:
        name = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        try:    _FC[k] = ImageFont.truetype(str(FONTS_DIR / name), size)
        except: _FC[k] = ImageFont.load_default()
    return _FC[k]

def _ww(f, t):
    try:    return int(f.getlength(t))
    except: bb = f.getbbox(t); return bb[2]-bb[0] if bb else 8


# ── Subtitle overlay ──────────────────────────────────────────────────────────
def draw_subtitle_frame(frame_arr: np.ndarray, text: str,
                        progress: float, accent_color: tuple) -> np.ndarray:
    """Draw karaoke-style subtitle on a video frame (numpy array)."""
    img  = Image.fromarray(frame_arr)
    draw = ImageDraw.Draw(img)
    f    = _font(28)

    words = text.split()
    if not words:
        return np.array(img)

    n_shown = max(1, int(len(words) * min(progress * 1.3, 1.0)))
    visible = " ".join(words[:n_shown])
    lines   = textwrap.wrap(visible, 65)[:2]
    if not lines:
        return np.array(img)

    LH  = 36
    PAD = 10
    bh  = len(lines) * LH + PAD * 2
    y1  = H - bh - 12

    # Background pill
    draw.rounded_rectangle([8, y1, W-8, H-12], radius=8, fill=(0,0,14))
    draw.rounded_rectangle([8, y1, 12, H-12], radius=4, fill=accent_color)

    for i, line in enumerate(lines):
        ty = y1 + PAD + i * LH
        draw.text((18, ty+2), line, font=f, fill=(0,0,0))
        draw.text((17, ty),   line, font=f, fill=(240,245,255))

    return np.array(img)


# ── Zoom/Ken Burns effect ─────────────────────────────────────────────────────
def apply_zoom(base_arr: np.ndarray, progress: float,
               zoom_in: bool = True, zoom_amount: float = 0.06) -> np.ndarray:
    """Apply subtle Ken Burns (zoom in/out) effect to a frame."""
    if zoom_amount == 0:
        return base_arr
    scale = 1.0 + zoom_amount * (progress if zoom_in else (1 - progress))
    sh, sw = base_arr.shape[:2]
    new_h = int(sh * scale)
    new_w = int(sw * scale)
    img   = Image.fromarray(base_arr).resize((new_w, new_h), Image.LANCZOS)
    # Crop back to original size (center crop)
    y0 = (new_h - sh) // 2
    x0 = (new_w - sw) // 2
    cropped = np.array(img)[y0:y0+sh, x0:x0+sw]
    return cropped


# ── Cross-fade transition ─────────────────────────────────────────────────────
def crossfade_frames(arr1: np.ndarray, arr2: np.ndarray, t: float) -> np.ndarray:
    """Blend two frames. t=0 → arr1, t=1 → arr2."""
    t = max(0.0, min(1.0, t))
    # Ease in-out
    t = t * t * (3 - 2 * t)
    return (arr1 * (1-t) + arr2 * t).astype(np.uint8)


# ── Progress bar ──────────────────────────────────────────────────────────────
def draw_progress_bar(draw: ImageDraw.Draw, frame_n: int, total_frames: int,
                      accent: tuple):
    progress = frame_n / max(total_frames, 1)
    bw = int(progress * W)
    draw.rectangle([0, 0, bw, 4], fill=accent)
    draw.rectangle([bw, 0, W, 4], fill=tuple(int(c*0.2) for c in accent))


# ── Scene renderer ────────────────────────────────────────────────────────────
def render_scene_frames(image_path: str, subtitle_text: str,
                        duration: float, accent_color: tuple,
                        frame_n_start: int, total_frames: int,
                        zoom_in: bool = True) -> List[np.ndarray]:
    """Render all frames for a single scene."""
    base_img = Image.open(image_path).convert("RGB").resize((W, H), Image.LANCZOS)
    base_arr = np.array(base_img)

    n_frames = max(1, int(duration * FPS))
    frames   = []

    FADE_FRAMES = max(1, int(FPS * 0.35))  # 0.35s fade
    TRANS_FRAMES = max(1, int(FPS * 0.4))  # 0.4s cross-fade (built into first/last)

    for fi in range(n_frames):
        p = fi / max(n_frames - 1, 1)

        # Ken Burns zoom
        frame = apply_zoom(base_arr, p, zoom_in=zoom_in, zoom_amount=0.05)

        # Fade in
        if fi < FADE_FRAMES:
            alpha = fi / FADE_FRAMES
            frame = (frame * alpha).astype(np.uint8)

        # Fade out
        if fi >= n_frames - FADE_FRAMES:
            alpha = (n_frames - fi) / FADE_FRAMES
            frame = (frame * max(0, alpha)).astype(np.uint8)

        # Subtitle
        frame = draw_subtitle_frame(frame, subtitle_text, p, accent_color)

        # Progress bar
        img  = Image.fromarray(frame)
        draw = ImageDraw.Draw(img)
        draw_progress_bar(draw, frame_n_start + fi, total_frames, accent_color)
        frame = np.array(img)

        frames.append(frame)

    return frames


# ── Assemble final video ──────────────────────────────────────────────────────
def assemble_video(scenes: list, out_path: str, accent_colors: list) -> str:
    """
    scenes: list of {image_path, audio_path, duration, subtitle, index}
    Writes MP4 to out_path. Returns out_path.
    """
    silent_path = out_path.replace(".mp4", "_silent.mp4")
    total_frames = sum(max(1, int(s["duration"] * FPS)) for s in scenes)

    print(f"[Editor] Rendering {len(scenes)} scenes, {total_frames} frames @ {FPS}fps")

    writer = imageio.get_writer(
        silent_path, fps=FPS, quality=8,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"]
    )

    for idx, scene in enumerate(scenes):
        acc = accent_colors[idx % len(accent_colors)]
        frames = render_scene_frames(
            image_path     = scene["image_path"],
            subtitle_text  = scene.get("subtitle", ""),
            duration       = scene["duration"],
            accent_color   = acc,
            frame_n_start  = sum(int(s["duration"]*FPS) for s in scenes[:idx]),
            total_frames   = total_frames,
            zoom_in        = (idx % 2 == 0),
        )
        for f in frames:
            writer.append_data(f)

        pct = int((idx+1)/len(scenes)*100)
        print(f"[Editor] Scene {idx+1}/{len(scenes)} — {pct}%")

    writer.close()

    # Merge audio
    audio_files = [s["audio_path"] for s in scenes if os.path.exists(s.get("audio_path",""))]
    if audio_files:
        _merge_audio_video(silent_path, audio_files, scenes, out_path)
        try: os.remove(silent_path)
        except: pass
    else:
        os.rename(silent_path, out_path)

    print(f"[Editor] Done → {out_path}")
    return out_path


def _merge_audio_video(video_path: str, audio_files: list,
                       scenes: list, out_path: str):
    """Merge per-scene audio with video using ffmpeg concat."""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    # Concatenate audio files
    combined_audio = out_path + "_combined.mp3"
    list_file = out_path + "_alist.txt"
    with open(list_file, "w") as f:
        for af in audio_files:
            f.write(f"file '{af}'\n")
    subprocess.run([ffmpeg, '-y', '-f', 'concat', '-safe', '0',
                    '-i', list_file, '-c', 'copy', combined_audio],
                   capture_output=True)
    try: os.remove(list_file)
    except: pass

    # Check for background music
    music_file = _find_music()
    if music_file:
        # Mix voiceover + bg music
        mixed_audio = out_path + "_mixed.mp3"
        subprocess.run([
            ffmpeg, '-y',
            '-i', combined_audio,
            '-i', music_file,
            '-filter_complex',
            '[0:a]volume=1.0[voice];[1:a]volume=0.08,aloop=loop=-1:size=2e+09[music];[voice][music]amix=inputs=2:duration=first[out]',
            '-map', '[out]',
            mixed_audio
        ], capture_output=True)
        if os.path.exists(mixed_audio):
            try: os.remove(combined_audio)
            except: pass
            combined_audio = mixed_audio

    # Final merge
    subprocess.run([
        ffmpeg, '-y',
        '-i', video_path,
        '-i', combined_audio,
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
        '-shortest', out_path
    ], capture_output=True)

    try: os.remove(combined_audio)
    except: pass


def _find_music() -> str:
    """Find background music file if available."""
    for ext in ["mp3", "ogg", "wav"]:
        for f in MUSIC_DIR.glob(f"*.{ext}"):
            return str(f)
    return ""
