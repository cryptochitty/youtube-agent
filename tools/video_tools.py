"""
Video assembly — combines images + audio into MP4.
Per-frame animated overlays: bullets, counter, bar chart, quote reveal.
"""
import os, subprocess, textwrap, math
from pathlib import Path
from typing import List
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio
from config import VIDEO_W, VIDEO_H, VIDEO_FPS, FONTS_DIR, MUSIC_DIR

W, H, FPS = VIDEO_W, VIDEO_H, VIDEO_FPS

# ── Fonts ─────────────────────────────────────────────────────────────────────
_FC = {}
def _font(size, bold=False):
    k = (size, bold)
    if k not in _FC:
        name = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        # 1. Bundled font (preferred)
        bundled = FONTS_DIR / name
        if bundled.exists():
            try:
                _FC[k] = ImageFont.truetype(str(bundled), size)
                return _FC[k]
            except Exception:
                pass
        # 2. System font paths
        sys_bold = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        ]
        sys_reg = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]
        for p in (sys_bold if bold else sys_reg):
            if os.path.exists(p):
                try:
                    _FC[k] = ImageFont.truetype(p, size)
                    return _FC[k]
                except Exception:
                    pass
        # 3. fc-match dynamic lookup
        try:
            pattern = "sans:bold" if bold else "sans"
            out = subprocess.run(["fc-match", "--format=%{file}", pattern],
                                 capture_output=True, text=True, timeout=3)
            p = out.stdout.strip()
            if out.returncode == 0 and p and os.path.exists(p):
                _FC[k] = ImageFont.truetype(p, size)
                return _FC[k]
        except Exception:
            pass
        _FC[k] = ImageFont.load_default()
    return _FC[k]

def _tw(draw_or_none, text, font):
    try:    return int(font.getlength(text))
    except:
        dummy = ImageDraw.Draw(Image.new("RGB", (1,1)))
        bb = dummy.textbbox((0,0), text, font=font)
        return bb[2] - bb[0]


# ── Animated overlay renderers ────────────────────────────────────────────────
def _overlay_bullets(img: Image.Image, bullets: list, progress: float,
                     accent, accent2) -> Image.Image:
    """Reveal bullet points one by one as scene plays."""
    if not bullets:
        return img
    draw = ImageDraw.Draw(img)

    n_vis = max(1, math.ceil(len(bullets) * min(progress * 1.6, 1.0)))
    bf    = _font(22)
    sf    = _font(17)
    LH    = 40
    CT, CB = 96, H - 22
    total_h = min(n_vis, len(bullets)) * LH
    sy = CT + max(0, (CB - CT - total_h) // 2)

    acc  = tuple(int(c) for c in accent)
    acc2 = tuple(int(c) for c in accent2)

    for i, bullet in enumerate(bullets[:n_vis]):
        by = sy + i * LH
        if by > CB - 26:
            break

        # Fade-in for the newest bullet
        fade = 1.0
        if i == n_vis - 1:
            slot_len = 1.0 / (len(bullets) * 1.6)
            slot_start = i * slot_len
            elapsed = progress - slot_start
            fade = min(1.0, elapsed / max(slot_len, 0.01))

        col   = acc if i % 2 == 0 else acc2
        fcol  = tuple(int(c * fade) for c in col)
        tcol  = tuple(int(c * fade) for c in (235, 240, 255))
        scol  = tuple(int(c * fade) for c in (0, 0, 0))

        # Bullet dot
        bx, bd = 24, by + 12
        draw.ellipse([bx-6, bd-6, bx+6, bd+6], fill=fcol)
        draw.ellipse([bx-3, bd-3, bx+3, bd+3], fill=scol)

        # Text (shadow + main)
        bl = textwrap.wrap(bullet, 40)[:2]
        for j, bline in enumerate(bl):
            font = bf if j == 0 else sf
            ty   = by + j * 20
            draw.text((40, ty+1), bline, font=font, fill=scol)
            draw.text((39, ty),   bline, font=font, fill=tcol)

    return img


def _overlay_counter(img: Image.Image, value_str: str, progress: float,
                     accent) -> Image.Image:
    """Animate a number counting up to its target."""
    import re
    draw = ImageDraw.Draw(img)
    m = re.search(r'(\d+(?:\.\d+)?)', str(value_str))
    if not m:
        return img

    target  = float(m.group(1))
    suffix  = str(value_str)[m.end():]
    t       = progress * progress * (3 - 2 * progress)   # ease in-out
    current = int(target * t)
    display = f"{current}{suffix}"

    acc = tuple(int(c) for c in accent)
    nf  = _font(72, bold=True)
    nw  = _tw(None, display, nf)
    nx  = (W - nw) // 2
    ny  = H // 2 - 58

    draw.text((nx+3, ny+3), display, font=nf, fill=(0,0,0))
    draw.text((nx+1, ny+1), display, font=nf,
              fill=tuple(int(c*0.28) for c in acc))
    draw.text((nx,   ny),   display, font=nf, fill=acc)

    # Subtle ring that expands with progress
    ring_r = int(50 + 30 * t)
    cx, cy = W//2, H//2 + 14
    col_r  = tuple(int(c * 0.18 * (1-t+0.3)) for c in acc)
    draw.ellipse([cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r], outline=col_r, width=2)

    return img


def _overlay_chart(img: Image.Image, chart_data: list, progress: float,
                   accent, accent2) -> Image.Image:
    """Grow bar chart upward."""
    if not chart_data:
        return img
    draw = ImageDraw.Draw(img)

    CL, CR = 48, W - 24
    CT, CB = 100, H - 42
    n      = len(chart_data)
    bw     = (CR - CL) / n
    pad    = bw * 0.18
    max_v  = max(d["value"] for d in chart_data) or 1

    t    = progress * progress * (3 - 2 * progress)
    vf   = _font(18, bold=True)
    acc  = tuple(int(c) for c in accent)
    acc2 = tuple(int(c) for c in accent2)

    for i, bar in enumerate(chart_data):
        bx    = CL + i * bw + pad
        bw2   = bw - pad * 2
        max_h = CB - CT
        bar_h = int(max_h * (bar["value"] / max_v) * t)
        if bar_h <= 0:
            continue

        by_top = CB - bar_h
        col    = acc if i % 2 == 0 else acc2

        # Bar gradient (lighter top)
        for yy in range(by_top, CB):
            mix = (yy - by_top) / max(bar_h, 1)
            row_c = tuple(int(c * (1.0 - mix * 0.35)) for c in col)
            draw.line([(int(bx), yy), (int(bx+bw2), yy)], fill=row_c)

        # Top highlight
        hl = tuple(min(255, int(c * 1.5)) for c in col)
        draw.rectangle([int(bx), by_top, int(bx+bw2), by_top+3], fill=hl)

        # Value label above bar
        if bar_h > 20:
            val_s = f"{int(bar['value'])}%"
            vw    = _tw(None, val_s, vf)
            draw.text((int(bx + bw2/2 - vw/2), by_top-20),
                      val_s, font=vf, fill=(230, 238, 255))

    return img


def _overlay_quote(img: Image.Image, text: str, progress: float,
                   accent) -> Image.Image:
    """Reveal quote word by word."""
    draw  = ImageDraw.Draw(img)
    words = text.split()
    if not words:
        return img

    n_shown = max(1, int(len(words) * min(progress * 1.35, 1.0)))
    shown   = " ".join(words[:n_shown])

    acc = tuple(int(c) for c in accent)
    qf  = _font(26)
    lines   = textwrap.wrap(shown, 50)[:5]
    total_h = len(lines) * 38
    ty      = (H - total_h) // 2 - 10

    for line in lines:
        lw = _tw(None, line, qf)
        draw.text(((W-lw)//2+2, ty+2), line, font=qf, fill=(0,0,0))
        draw.text(((W-lw)//2,   ty),   line, font=qf, fill=(232, 238, 255))
        ty += 38

    # Closing quote fades in at end
    if progress > 0.75:
        alpha = (progress - 0.75) / 0.25
        cqf = _font(80, bold=True)
        cw  = _tw(None, "\u201D", cqf)
        col = tuple(int(c * alpha * 0.25) for c in acc)
        draw.text((W - cw - 22, ty - 16), "\u201D", font=cqf, fill=col)

    return img


# ── Subtitle overlay ──────────────────────────────────────────────────────────
def draw_subtitle_frame(frame_arr: np.ndarray, text: str,
                        progress: float, accent_color: tuple) -> np.ndarray:
    img  = Image.fromarray(frame_arr)
    draw = ImageDraw.Draw(img)
    f    = _font(12)

    words = text.split()
    if not words:
        return np.array(img)

    n_shown = max(1, int(len(words) * min(progress * 1.3, 1.0)))
    visible = " ".join(words[:n_shown])
    lines   = textwrap.wrap(visible, 48)[:2]
    if not lines:
        return np.array(img)

    LH, PAD = 28, 7
    bh = len(lines) * LH + PAD * 2
    y1 = H - bh - 10

    draw.rounded_rectangle([6, y1, W-6, H-10], radius=6, fill=(0,0,12,220))
    draw.rounded_rectangle([6, y1, 10, H-10], radius=4, fill=accent_color)

    for i, line in enumerate(lines):
        ty = y1 + PAD + i * LH
        draw.text((16, ty+2), line, font=f, fill=(0,0,0))
        draw.text((15, ty),   line, font=f, fill=(238, 243, 255))

    return np.array(img)


# ── Ken Burns zoom ────────────────────────────────────────────────────────────
def apply_zoom(base_arr: np.ndarray, progress: float,
               zoom_in: bool = True, zoom_amount: float = 0.04) -> np.ndarray:
    if zoom_amount == 0:
        return base_arr
    scale = 1.0 + zoom_amount * (progress if zoom_in else (1 - progress))
    sh, sw = base_arr.shape[:2]
    img    = Image.fromarray(base_arr).resize(
        (int(sw*scale), int(sh*scale)), Image.LANCZOS)
    nh, nw = int(sh*scale), int(sw*scale)
    y0 = (nh - sh) // 2
    x0 = (nw - sw) // 2
    return np.array(img)[y0:y0+sh, x0:x0+sw]


# ── Progress bar ──────────────────────────────────────────────────────────────
def draw_progress_bar(draw: ImageDraw.Draw, frame_n: int,
                      total_frames: int, accent: tuple):
    prog = frame_n / max(total_frames, 1)
    bw   = int(prog * W)
    draw.rectangle([0, 0, bw, 4],  fill=accent)
    draw.rectangle([bw, 0, W, 4],  fill=tuple(int(c*0.18) for c in accent))


# ── Scene renderer ────────────────────────────────────────────────────────────
def render_scene_frames(
    image_path: str, subtitle_text: str, duration: float,
    accent_color: tuple, frame_n_start: int, total_frames: int,
    zoom_in: bool = True, anim_data: dict = None,
) -> List[np.ndarray]:
    base = Image.open(image_path).convert("RGB").resize((W, H), Image.LANCZOS)
    base_arr  = np.array(base)
    n_frames  = max(1, int(duration * FPS))
    anim_data = anim_data or {"type": "none"}
    atype     = anim_data.get("type", "none")
    frames    = []

    FADE = max(1, int(FPS * 0.3))

    for fi in range(n_frames):
        p = fi / max(n_frames - 1, 1)

        # Ken Burns (reduced zoom for animation-heavy scenes)
        za = 0.02 if atype in ("bullets", "chart") else 0.04
        frame = apply_zoom(base_arr, p, zoom_in=zoom_in, zoom_amount=za)

        # Animated content overlay
        frame_img = Image.fromarray(frame)
        if atype == "bullets":
            frame_img = _overlay_bullets(
                frame_img, anim_data.get("bullets", []), p,
                anim_data.get("accent", accent_color),
                anim_data.get("accent2", accent_color))
        elif atype == "counter":
            frame_img = _overlay_counter(
                frame_img, anim_data.get("value", "0"), p,
                anim_data.get("accent", accent_color))
        elif atype == "chart":
            frame_img = _overlay_chart(
                frame_img, anim_data.get("data", []), p,
                anim_data.get("accent", accent_color),
                anim_data.get("accent2", accent_color))
        elif atype == "quote":
            frame_img = _overlay_quote(
                frame_img, anim_data.get("text", ""), p,
                anim_data.get("accent", accent_color))
        frame = np.array(frame_img)

        # Fade in / out
        if fi < FADE:
            frame = (frame * (fi / FADE)).astype(np.uint8)
        if fi >= n_frames - FADE:
            frame = (frame * max(0, (n_frames - fi) / FADE)).astype(np.uint8)

        # Subtitle
        frame = draw_subtitle_frame(frame, subtitle_text, p, accent_color)

        # Progress bar
        pimg  = Image.fromarray(frame)
        pdraw = ImageDraw.Draw(pimg)
        draw_progress_bar(pdraw, frame_n_start + fi, total_frames, accent_color)
        frames.append(np.array(pimg))

    return frames


# ── Assemble final video ──────────────────────────────────────────────────────
def assemble_video(scenes: list, out_path: str, accent_colors: list) -> str:
    silent_path  = out_path.replace(".mp4", "_silent.mp4")
    total_frames = sum(max(1, int(s["duration"] * FPS)) for s in scenes)

    print(f"[Editor] {len(scenes)} scenes, {total_frames} frames @ {FPS}fps")

    writer = imageio.get_writer(
        silent_path, fps=FPS, quality=8,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )

    frame_cursor = 0
    for idx, scene in enumerate(scenes):
        acc = tuple(int(c) for c in accent_colors[idx % len(accent_colors)])
        frames = render_scene_frames(
            image_path    = scene["image_path"],
            subtitle_text = scene.get("subtitle", ""),
            duration      = scene["duration"],
            accent_color  = acc,
            frame_n_start = frame_cursor,
            total_frames  = total_frames,
            zoom_in       = (idx % 2 == 0),
            anim_data     = scene.get("anim_data", {"type": "none"}),
        )
        for f in frames:
            writer.append_data(f)
        frame_cursor += len(frames)
        print(f"[Editor] Scene {idx+1}/{len(scenes)} — {int((idx+1)/len(scenes)*100)}%")

    writer.close()

    # Merge audio
    audio_files = [s["audio_path"] for s in scenes
                   if os.path.exists(s.get("audio_path", ""))]
    if audio_files:
        _merge_audio(silent_path, audio_files, scenes, out_path)
        try: os.remove(silent_path)
        except: pass
    else:
        os.rename(silent_path, out_path)

    print(f"[Editor] Done → {out_path}")
    return out_path


def _merge_audio(video_path, audio_files, scenes, out_path):
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

    combined = out_path + "_comb.mp3"
    lst_file = out_path + "_alist.txt"
    with open(lst_file, "w") as f:
        for af in audio_files:
            f.write(f"file '{af}'\n")
    subprocess.run([ffmpeg, '-y', '-f', 'concat', '-safe', '0',
                    '-i', lst_file, '-c', 'copy', combined],
                   capture_output=True)
    try: os.remove(lst_file)
    except: pass

    music = _find_music()
    if music:
        mixed = out_path + "_mixed.mp3"
        subprocess.run([
            ffmpeg, '-y', '-i', combined, '-i', music,
            '-filter_complex',
            '[0:a]volume=1.0[v];[1:a]volume=0.08,aloop=loop=-1:size=2e+09[m];[v][m]amix=inputs=2:duration=first[out]',
            '-map', '[out]', mixed,
        ], capture_output=True)
        if os.path.exists(mixed):
            try: os.remove(combined)
            except: pass
            combined = mixed

    subprocess.run([
        ffmpeg, '-y', '-i', video_path, '-i', combined,
        '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', out_path,
    ], capture_output=True)
    try: os.remove(combined)
    except: pass


def _find_music():
    for ext in ["mp3", "ogg", "wav"]:
        for f in MUSIC_DIR.glob(f"*.{ext}"):
            return str(f)
    return ""
