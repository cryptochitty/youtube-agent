"""
Image generation — PIL-based scene generator with animation metadata.
Each scene produces a background image + anim_data dict for per-frame overlays.
"""
import math, random, textwrap, re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from config import VIDEO_W, VIDEO_H, FONTS_DIR, IMAGE_PROVIDER, HF_API_TOKEN, get_palette

W, H = VIDEO_W, VIDEO_H

# ── Fonts ─────────────────────────────────────────────────────────────────────
_FC = {}
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    k = (size, bold)
    if k not in _FC:
        fname = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        try:    _FC[k] = ImageFont.truetype(str(FONTS_DIR / fname), size)
        except: _FC[k] = ImageFont.load_default()
    return _FC[k]

def _tw(draw, text, font):
    try:    return int(font.getlength(text))
    except: bb = draw.textbbox((0,0), text, font=font); return bb[2]-bb[0]


# ── Background ─────────────────────────────────────────────────────────────────
def _gradient_bg(palette: dict, seed: int = 0) -> Image.Image:
    bg1 = np.array(palette["bg1"], dtype=float)
    bg2 = np.array(palette["bg2"], dtype=float)
    acc = np.array(palette["accent"], dtype=float)

    t = np.linspace(0, 1, H)[:, None, None]
    arr = (bg1 * (1 - t) + bg2 * t) * np.ones((H, W, 3))

    # Radial glow top-right
    random.seed(seed)
    cx, cy = int(W * 0.75), int(H * 0.22)
    ys, xs = np.mgrid[0:H, 0:W]
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    glow = np.clip(1 - dist / 380, 0, 1) * 0.10
    arr += acc * glow[:, :, None]

    # Second subtle glow bottom-left
    dist2 = np.sqrt((xs - W*0.15) ** 2 + (ys - H*0.85) ** 2)
    glow2 = np.clip(1 - dist2 / 280, 0, 1) * 0.05
    arr += np.array(palette["accent2"], dtype=float) * glow2[:, :, None]

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _decor(draw: ImageDraw.Draw, palette: dict, seed: int = 0):
    random.seed(seed)
    acc  = palette["accent"]
    acc2 = palette["accent2"]

    # Border bars
    draw.rectangle([0, 0, W, 3],       fill=acc)
    draw.rectangle([0, 0, 3, H],       fill=tuple(int(c*0.5) for c in acc2))
    draw.rectangle([0, H-3, W, H],     fill=acc2)
    draw.rectangle([W-3, 0, W, H],     fill=tuple(int(c*0.3) for c in acc))

    # Corner lines top-right
    for i in range(7):
        off = 14 + i * 16
        draw.line([(W-off, 0), (W, off)],
                  fill=tuple(int(c*0.10) for c in acc), width=1)

    # Grid dots
    for gx in range(0, W, 80):
        for gy in range(0, H, 80):
            draw.ellipse([gx-1, gy-1, gx+1, gy+1],
                         fill=tuple(int(c*0.08) for c in acc))

    # Large faint background circle
    cx = random.randint(W//2, W)
    cy = random.randint(0, H//2)
    cr = random.randint(80, 180)
    draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr],
                 fill=tuple(int(c*0.04) for c in acc))


# ── Section header ─────────────────────────────────────────────────────────────
def _draw_header(draw, palette, title: str, section_num: int) -> int:
    """Draw badge + title. Returns y where content starts."""
    acc    = palette["accent"]
    text_c = palette["text"]

    bx, by, br = 36, 36, 24
    for r2, a in [(30, 0.12), (26, 0.20)]:
        draw.ellipse([bx-r2, by-r2, bx+r2, by+r2],
                     fill=tuple(int(c*a) for c in acc))
    draw.ellipse([bx-br, by-br, bx+br, by+br], fill=acc)
    nf = _font(20, bold=True)
    ns = str(section_num)
    nw = _tw(draw, ns, nf)
    draw.text((bx-nw//2, by-13), ns, font=nf, fill=(0,0,0))

    tf = _font(42, bold=True)
    ty = 12
    for line in textwrap.wrap(title, 30)[:2]:
        draw.text((70, ty+1), line, font=tf, fill=(0,0,0))
        draw.text((69, ty),   line, font=tf, fill=text_c)
        ty += 50

    div_y = max(76, ty + 2)
    draw.rectangle([14, div_y, W-14, div_y+2],
                   fill=tuple(int(c*0.35) for c in acc))
    return div_y + 8


# ── Scene shell renderers ──────────────────────────────────────────────────────
def _shell_intro(draw, palette, topic: str, subtitle: str):
    acc    = palette["accent"]
    acc2   = palette["accent2"]
    text_c = palette["text"]

    # Radial circles behind text
    for r, a in [(150, 0.09), (110, 0.14), (70, 0.20)]:
        col = tuple(int(c*a) for c in acc)
        draw.ellipse([W//2-r, H//2-r-15, W//2+r, H//2+r-15], fill=col)

    # Channel badge
    draw.rounded_rectangle([10, 8, 118, 32], radius=4, fill=acc2)
    draw.text((18, 10), "AI VIDEO", font=_font(16, bold=True), fill=(0,0,0))

    # Topic title
    tf     = _font(60, bold=True)
    lines  = textwrap.wrap(topic.upper(), 20)[:2]
    total_h = len(lines) * 72
    ty     = (H - total_h) // 2 - 15
    for i, line in enumerate(lines):
        lw = _tw(draw, line, tf)
        x  = (W - lw) // 2
        draw.text((x+3, ty+3), line, font=tf, fill=(0,0,0))
        draw.text((x,   ty),   line, font=tf,
                  fill=acc if i == 0 else text_c)
        ty += 72

    # Underline
    draw.rectangle([(W-240)//2, ty+4, (W+240)//2, ty+8], fill=acc2)

    # Subtitle
    if subtitle:
        sf = _font(24)
        for j, sl in enumerate(textwrap.wrap(subtitle, 58)[:2]):
            slw = _tw(draw, sl, sf)
            draw.text(((W-slw)//2, ty+16+j*30), sl, font=sf,
                      fill=tuple(int(c*0.68) for c in text_c))

    # Bottom strip
    draw.rectangle([0, H-40, W, H-3], fill=tuple(int(c*0.22) for c in acc))
    draw.text((16, H-32), "▶  WATCH NOW", font=_font(20), fill=acc)


def _shell_section(draw, palette, title: str, idx: int):
    acc = palette["accent"]
    # Dark card in content area
    draw.rounded_rectangle([10, 88, W-10, H-18], radius=8,
                            fill=tuple(int(c*0.28) for c in palette["bg2"]))
    draw.rounded_rectangle([10, 88, 14, H-18], radius=4, fill=acc)
    _draw_header(draw, palette, title, idx)


def _shell_stat(draw, palette, label: str, title: str):
    acc    = palette["accent"]
    text_c = palette["text"]

    # Concentric circles
    for r, a in [(120, 0.07), (90, 0.11), (60, 0.17)]:
        draw.ellipse([W//2-r, H//2-r+8, W//2+r, H//2+r+8],
                     fill=tuple(int(c*a) for c in acc))

    # Title
    tf = _font(34, bold=True)
    ty = 18
    for line in textwrap.wrap(title, 38)[:2]:
        lw = _tw(draw, line, tf)
        draw.text(((W-lw)//2, ty), line, font=tf, fill=text_c)
        ty += 40

    # Label (static)
    if label:
        lf = _font(26)
        ly = H//2 + 76
        for line in textwrap.wrap(label[:80], 44)[:2]:
            lw = _tw(draw, line, lf)
            draw.text(((W-lw)//2, ly), line, font=lf,
                      fill=tuple(int(c*0.72) for c in text_c))
            ly += 34


def _shell_quote(draw, palette, title: str, idx: int):
    acc    = palette["accent"]
    text_c = palette["text"]

    # Large faint quote mark
    draw.text((28, -28), "\u201C", font=_font(200, bold=True),
              fill=tuple(int(c*0.07) for c in acc))

    # Topic label
    draw.text((18, 14), f"  {title[:52]}", font=_font(20),
              fill=tuple(int(c*0.50) for c in text_c))

    # Subtle content panel
    draw.rounded_rectangle([28, 76, W-28, H-46], radius=6,
                            fill=tuple(int(c*0.04) for c in palette["bg2"]))


def _shell_chart(draw, palette, title: str, idx: int, labels: list):
    acc    = palette["accent"]
    text_c = palette["text"]

    _draw_header(draw, palette, title, idx)

    CL, CR = 48, W-24
    CT, CB = 100, H-42

    # Axes
    draw.line([(CL, CT), (CL, CB)], fill=tuple(int(c*0.4) for c in text_c), width=2)
    draw.line([(CL, CB), (CR, CB)], fill=tuple(int(c*0.4) for c in text_c), width=2)

    # X labels
    lf = _font(16)
    if labels:
        bw = (CR - CL) / len(labels)
        for i, label in enumerate(labels[:8]):
            bx = CL + (i + 0.5) * bw
            lw = _tw(draw, label[:8], lf)
            draw.text((int(bx-lw//2), CB+4), label[:8], font=lf,
                      fill=tuple(int(c*0.55) for c in text_c))

    # Grid lines
    for pct in [0.25, 0.50, 0.75, 1.0]:
        gy = int(CB - (CB-CT) * pct)
        draw.line([(CL, gy), (CR, gy)],
                  fill=tuple(int(c*0.08) for c in text_c), width=1)


def _shell_cta(draw, palette):
    acc    = palette["accent"]
    text_c = palette["text"]

    for r, a in [(180, 0.05), (140, 0.09), (100, 0.14), (65, 0.20)]:
        draw.ellipse([W//2-r, H//2-r, W//2+r, H//2+r],
                     fill=tuple(int(c*a) for c in acc))

    tf = _font(52, bold=True)
    for i, line in enumerate(["THANKS FOR", "WATCHING!"]):
        lw = _tw(draw, line, tf)
        draw.text(((W-lw)//2+2, H//2-64+i*62+2), line, font=tf, fill=(0,0,0))
        draw.text(((W-lw)//2,   H//2-64+i*62),   line, font=tf, fill=text_c)

    draw.rectangle([0, H-52, W, H-3], fill=tuple(int(c*0.25) for c in acc))
    prompt = "  Like   |   Subscribe   |   Comment  "
    pf = _font(22)
    pw = _tw(draw, prompt, pf)
    draw.text(((W-pw)//2, H-42), prompt, font=pf, fill=acc)


# ── Main entry ────────────────────────────────────────────────────────────────
def generate_scene_image(
    section_index: int, section_title: str, section_content: str,
    topic: str, total_sections: int, out_path: str, visual_prompt: str = "",
) -> tuple:
    """Returns (out_path, anim_data)."""
    palette = get_palette(topic)

    if IMAGE_PROVIDER == "huggingface" and HF_API_TOKEN and visual_prompt:
        try:
            p = _hf_generate(visual_prompt, out_path, palette)
            if p:
                return p, {"type": "none"}
        except Exception as e:
            print(f"[Image] HF failed: {e}")

    anim = _local_generate(section_index, section_title, section_content,
                            topic, total_sections, out_path, palette)
    return out_path, anim


def _local_generate(idx, title, content, topic, total, out_path, palette):
    img  = _gradient_bg(palette, seed=idx)
    draw = ImageDraw.Draw(img)
    _decor(draw, palette, seed=idx)

    anim = {"type": "none"}

    if idx == 0:
        _shell_intro(draw, palette, topic, _first_sentence(content))
        # intro fully rendered — no overlay needed

    elif idx >= total - 1:
        _shell_cta(draw, palette)
        anim = {"type": "pulse"}

    else:
        bullets    = _extract_bullets(content)
        stat       = _extract_stat(content)
        chart_data = _extract_chart_data(content)

        if chart_data and len(chart_data) >= 3:
            labels = [d["label"] for d in chart_data]
            _shell_chart(draw, palette, title, idx, labels)
            anim = {"type": "chart", "data": chart_data,
                    "accent": palette["accent"], "accent2": palette["accent2"]}

        elif stat and len(bullets) < 2:
            _shell_stat(draw, palette, stat[1], title)
            anim = {"type": "counter", "value": stat[0], "label": stat[1],
                    "accent": palette["accent"]}

        elif len(bullets) >= 2:
            _shell_section(draw, palette, title, idx)
            anim = {"type": "bullets", "bullets": bullets[:5],
                    "accent": palette["accent"], "accent2": palette["accent2"]}

        else:
            _shell_quote(draw, palette, title, idx)
            anim = {"type": "quote", "text": _best_quote(content),
                    "accent": palette["accent"]}

    # Progress bar
    if total > 1:
        pw = int((idx / max(total-1, 1)) * W)
        draw.rectangle([0, H-5, pw, H], fill=palette["accent"])
        draw.rectangle([pw, H-5, W, H],
                       fill=tuple(int(c*0.18) for c in palette["accent"]))

    img.save(out_path, "JPEG", quality=92)
    return anim


# ── Helpers ───────────────────────────────────────────────────────────────────
def _first_sentence(text):
    m = re.match(r"([^.!?]+[.!?])", text.strip())
    return m.group(1)[:88] if m else text[:88]

def _extract_bullets(text):
    items = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|[-•*]\s*)(.+)', text)
    if not items:
        sentences = re.split(r'[.!?]+', text)
        items = [s.strip() for s in sentences if len(s.strip()) > 15]
    return [i[:88] for i in items[:6] if i.strip()]

def _extract_stat(text):
    m = re.search(
        r'(\d+(?:\.\d+)?(?:\s*%|x|X|\s*billion|\s*million|\s*trillion|\s*K)?)', text)
    if m and len(m.group(1)) >= 2:
        val   = m.group(1).strip()
        label = text[:80].replace(val, "").strip()[:60]
        return val, label
    return None

def _extract_chart_data(text):
    """Detect comparison patterns like 'A: 40%, B: 60%, C: 80%'."""
    items = re.findall(
        r'([A-Za-z][A-Za-z\s]{1,14}?)[\s:]+(\d+(?:\.\d+)?)(?:\s*%)?', text)
    if len(items) >= 3:
        return [{"label": k.strip()[:10], "value": float(v)}
                for k, v in items[:8] if float(v) > 0]
    return []

def _best_quote(text):
    sentences = re.split(r'[.!?]+', text)
    best = max((s.strip() for s in sentences if len(s.strip()) > 20),
               key=len, default=text[:120])
    return best[:150]


# ── HuggingFace ───────────────────────────────────────────────────────────────
def _hf_generate(prompt, out_path, palette):
    import requests
    URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    r = requests.post(URL, headers={"Authorization": f"Bearer {HF_API_TOKEN}"},
                      json={"inputs": f"cinematic 4K, {prompt}, professional, sharp"},
                      timeout=60)
    if r.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(r.content)
        return out_path
    return ""


# ── Thumbnail ─────────────────────────────────────────────────────────────────
def generate_thumbnail(topic: str, title: str, out_path: str) -> str:
    palette = get_palette(topic)
    img  = _gradient_bg(palette, seed=99)
    draw = ImageDraw.Draw(img)
    _decor(draw, palette, seed=99)

    acc    = palette["accent"]
    acc2   = palette["accent2"]
    text_c = palette["text"]

    # Glow behind title
    for r, a in [(240, 0.09), (180, 0.14), (120, 0.20)]:
        col = tuple(int(c*a) for c in acc)
        draw.ellipse([W//2-r, H//2-r+25, W//2+r, H//2+r+25], fill=col)

    # "NEW" badge
    draw.rounded_rectangle([10, 8, 96, 32], radius=4, fill=acc2)
    draw.text((18, 10), "NEW VIDEO", font=_font(16, bold=True), fill=(0,0,0))

    # Title
    title_lines = textwrap.wrap(title.upper(), 16)[:3]
    tf = _font(68, bold=True)
    ty = H//2 - len(title_lines) * 42 - 8
    for i, line in enumerate(title_lines):
        lw = _tw(draw, line, tf)
        x  = (W - lw) // 2
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,4),(4,0),(-4,0),(0,-4)]:
            draw.text((x+dx, ty+dy), line, font=tf, fill=(0,0,0))
        draw.text((x, ty), line, font=tf,
                  fill=acc if i == 0 else text_c)
        ty += 82

    # Underline
    uw = 260
    draw.rectangle([(W-uw)//2, ty+2, (W+uw)//2, ty+6], fill=acc2)

    # Bottom strip
    draw.rectangle([0, H-42, W, H-3], fill=tuple(int(c*0.28) for c in acc))
    draw.text((14, H-34), f"▶  {topic[:55]}", font=_font(20), fill=text_c)

    img.save(out_path, "JPEG", quality=95)
    return out_path
