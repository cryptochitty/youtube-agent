"""
Image generation — PIL-based motion graphics (always works) +
optional Stable Diffusion via HuggingFace Inference API.
"""
import math, random, textwrap, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from config import VIDEO_W, VIDEO_H, FONTS_DIR, IMAGE_PROVIDER, HF_API_TOKEN, get_palette

# ── Font helpers ──────────────────────────────────────────────────────────────
_FONT_CACHE = {}

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _FONT_CACHE:
        fname = "NotoSans-Bold.ttf" if bold else "NotoSans-Regular.ttf"
        try:
            _FONT_CACHE[key] = ImageFont.truetype(str(FONTS_DIR / fname), size)
        except Exception:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]

def _text_w(draw, text, font):
    try:    return int(font.getlength(text))
    except: bb = draw.textbbox((0,0), text, font=font); return bb[2]-bb[0]

# ── Gradient background ───────────────────────────────────────────────────────
def _gradient_bg(palette: dict) -> Image.Image:
    img = Image.new("RGB", (VIDEO_W, VIDEO_H))
    arr = np.zeros((VIDEO_H, VIDEO_W, 3), dtype=np.uint8)
    bg1, bg2 = np.array(palette["bg1"]), np.array(palette["bg2"])
    for y in range(VIDEO_H):
        t = y / VIDEO_H
        # Radial gradient effect
        cx_factor = abs(math.sin(y / VIDEO_H * math.pi)) * 0.15
        row = (bg1 * (1-t) + bg2 * t).astype(np.uint8)
        arr[y] = row
    return Image.fromarray(arr)


def _add_geometric_decor(draw: ImageDraw.Draw, palette: dict, seed: int = 0):
    """Add subtle geometric decorations: circles, lines, dots."""
    random.seed(seed)
    acc  = palette["accent"]
    acc2 = palette["accent2"]
    W, H = VIDEO_W, VIDEO_H

    # Large background circles (subtle)
    for _ in range(3):
        cx = random.randint(0, W)
        cy = random.randint(0, H)
        cr = random.randint(80, 250)
        col = random.choice([acc, acc2])
        alpha_col = tuple(int(c * 0.06) for c in col)
        draw.ellipse([cx-cr, cy-cr, cx+cr, cy+cr], fill=alpha_col)

    # Grid dots (subtle)
    for gx in range(0, W, 60):
        for gy in range(0, H, 60):
            draw.ellipse([gx-1, gy-1, gx+1, gy+1],
                         fill=tuple(int(c*0.12) for c in acc))

    # Top accent bar
    draw.rectangle([0, 0, W, 4], fill=acc)

    # Bottom accent line
    draw.rectangle([0, H-3, W, H], fill=acc2)

    # Left side accent bar
    draw.rectangle([0, 0, 4, H], fill=tuple(int(c*0.6) for c in acc2))

    # Diagonal corner decoration (top-right)
    for i in range(5):
        off = 20 + i * 18
        draw.line([(W-off, 0), (W, off)],
                  fill=tuple(int(c*0.15) for c in acc), width=1)


# ── Scene type renderers ──────────────────────────────────────────────────────
def _render_title_card(draw, palette, title: str, subtitle: str = ""):
    """Full-center title card."""
    W, H = VIDEO_W, VIDEO_H
    acc  = palette["accent"]
    text_c = palette["text"]

    # Title (large, centered)
    title_font = _font(72, bold=True)
    lines = textwrap.wrap(title, 22)[:3]
    total_h = len(lines) * 86 + (30 if subtitle else 0)
    y = (H - total_h) // 2

    for i, line in enumerate(lines):
        tw = _text_w(draw, line, title_font)
        x  = (W - tw) // 2
        # Shadow
        draw.text((x+3, y+3), line, font=title_font, fill=(0,0,0))
        draw.text((x, y), line, font=title_font, fill=text_c)
        # Highlight word (first line, accent color glow)
        if i == 0:
            draw.text((x, y), line, font=title_font, fill=acc)
        y += 86

    # Subtitle
    if subtitle:
        sf = _font(32)
        sw = _text_w(draw, subtitle, sf)
        draw.text(((W-sw)//2, y+10), subtitle, font=sf,
                  fill=tuple(int(c*0.75) for c in text_c))

    # Accent underline below first line
    first_lines = textwrap.wrap(title, 22)[:1]
    if first_lines:
        fl = first_lines[0]
        tw = _text_w(draw, fl, title_font)
        lx = (W - tw) // 2
        ly = (H - total_h) // 2 + 82
        draw.rectangle([lx, ly, lx + tw, ly + 4], fill=acc)


def _render_bullet_card(draw, palette, title: str, bullets: list, index: int = 0):
    """Section card with title + bullet points."""
    W, H = VIDEO_W, VIDEO_H
    acc   = palette["accent"]
    acc2  = palette["accent2"]
    text_c = palette["text"]
    dim_c  = tuple(int(c * 0.65) for c in text_c)

    # Section number badge (top-left)
    badge_r = 32
    badge_x, badge_y = 60, 60
    draw.ellipse([badge_x-badge_r, badge_y-badge_r,
                  badge_x+badge_r, badge_y+badge_r], fill=acc)
    nf = _font(28, bold=True)
    ns = str(index + 1)
    nw = _text_w(draw, ns, nf)
    draw.text((badge_x - nw//2, badge_y - 16), ns, font=nf, fill=(0,0,0))

    # Section title
    tf = _font(52, bold=True)
    title_lines = textwrap.wrap(title, 30)[:2]
    ty = 35
    for line in title_lines:
        draw.text((115, ty), line, font=tf, fill=text_c)
        ty += 60

    # Divider
    draw.rectangle([60, ty+8, W-60, ty+10], fill=acc)

    # Bullet points
    bf = _font(34)
    bullet_y = ty + 30
    for i, bullet in enumerate(bullets[:5]):
        col = acc if i % 2 == 0 else acc2
        # Bullet icon
        bx, by = 70, bullet_y + 16
        draw.ellipse([bx-8, by-8, bx+8, by+8], fill=col)
        draw.ellipse([bx-4, by-4, bx+4, by+4], fill=(0,0,0))
        # Text
        bl = textwrap.wrap(bullet, 52)[:2]
        for j, bl_line in enumerate(bl):
            draw.text((95, bullet_y + j*40), bl_line, font=bf, fill=text_c)
        bullet_y += max(50, len(bl)*40 + 14)
        if bullet_y > H - 60:
            break


def _render_quote_card(draw, palette, quote: str, context: str = ""):
    """Large quote display."""
    W, H = VIDEO_W, VIDEO_H
    acc   = palette["accent"]
    text_c = palette["text"]

    # Large quotation mark
    qf = _font(180, bold=True)
    draw.text((50, -20), "\u201C", font=qf,
              fill=tuple(int(c*0.15) for c in acc))

    # Quote text
    qf2 = _font(44)
    q_lines = textwrap.wrap(quote, 38)[:5]
    total_h = len(q_lines) * 58
    y = (H - total_h) // 2 - 20
    for line in q_lines:
        lw = _text_w(draw, line, qf2)
        draw.text(((W-lw)//2, y), line, font=qf2, fill=text_c)
        y += 58

    # Accent line
    draw.rectangle([(W-200)//2, y+12, (W+200)//2, y+16], fill=acc)

    # Context/attribution
    if context:
        cf = _font(28)
        cw = _text_w(draw, context, cf)
        draw.text(((W-cw)//2, y+28), context, font=cf,
                  fill=tuple(int(c*0.6) for c in text_c))


def _render_stat_card(draw, palette, stat_value: str, stat_label: str,
                      context: str = ""):
    """Big stat / number highlight card."""
    W, H = VIDEO_W, VIDEO_H
    acc   = palette["accent"]
    acc2  = palette["accent2"]
    text_c = palette["text"]

    # Big number
    sf = _font(130, bold=True)
    sw = _text_w(draw, stat_value, sf)
    draw.text(((W-sw)//2 + 3, H//2 - 100 + 3), stat_value, font=sf, fill=(0,0,0))
    draw.text(((W-sw)//2,     H//2 - 100),      stat_value, font=sf, fill=acc)

    # Label
    lf = _font(44)
    lw = _text_w(draw, stat_label, lf)
    draw.text(((W-lw)//2, H//2 + 50), stat_label, font=lf, fill=text_c)

    # Context
    if context:
        cf = _font(28)
        for i, cl in enumerate(textwrap.wrap(context, 55)[:2]):
            clw = _text_w(draw, cl, cf)
            draw.text(((W-clw)//2, H//2 + 110 + i*36), cl, font=cf,
                      fill=tuple(int(c*0.65) for c in text_c))


def _render_intro_card(draw, palette, topic: str, subtitle: str = ""):
    """Opening intro card with topic + channel style."""
    W, H = VIDEO_W, VIDEO_H
    acc   = palette["accent"]
    acc2  = palette["accent2"]
    text_c = palette["text"]

    # Topic
    tf = _font(68, bold=True)
    t_lines = textwrap.wrap(topic, 24)[:2]
    ty = H//2 - len(t_lines)*40 - 30
    for i, line in enumerate(t_lines):
        lw = _text_w(draw, line, tf)
        col = acc if i == 0 else text_c
        draw.text(((W-lw)//2 + 2, ty+2), line, font=tf, fill=(0,0,0))
        draw.text(((W-lw)//2,     ty),   line, font=tf, fill=col)
        ty += 80

    # Subtitle
    if subtitle:
        sf = _font(32)
        sw = _text_w(draw, subtitle, sf)
        draw.text(((W-sw)//2, ty+10), subtitle, font=sf,
                  fill=tuple(int(c*0.7) for c in text_c))
        ty += 48

    # Accent underline
    draw.rectangle([(W-300)//2, ty+8, (W+300)//2, ty+12], fill=acc2)


def _render_cta_card(draw, palette, message: str):
    """Call-to-action outro card."""
    W, H = VIDEO_W, VIDEO_H
    acc   = palette["accent"]
    acc2  = palette["accent2"]
    text_c = palette["text"]

    # Background circles
    for r, a in [(200, 0.06), (150, 0.09), (100, 0.12)]:
        col = tuple(int(c*a) for c in acc)
        draw.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=col)

    # Main message
    mf = _font(56, bold=True)
    m_lines = textwrap.wrap(message, 24)[:3]
    ty = H//2 - len(m_lines)*33
    for line in m_lines:
        lw = _text_w(draw, line, mf)
        draw.text(((W-lw)//2, ty), line, font=mf, fill=text_c)
        ty += 66

    # Subscribe prompt
    prompt = "👍  Like  |  🔔  Subscribe  |  💬  Comment"
    pf = _font(30)
    pw = _text_w(draw, prompt, pf)
    draw.text(((W-pw)//2, ty+20), prompt, font=pf,
              fill=tuple(int(c*0.8) for c in acc))


# ── Main scene image generator ────────────────────────────────────────────────
SCENE_TYPES = ["intro", "title", "bullet", "quote", "stat", "bullet", "cta"]

def generate_scene_image(
    section_index: int,
    section_title: str,
    section_content: str,
    topic: str,
    total_sections: int,
    out_path: str,
    visual_prompt: str = "",
) -> str:
    """Generate one scene image. Returns out_path."""
    palette = get_palette(topic)

    # Try HuggingFace Stable Diffusion if configured
    if IMAGE_PROVIDER == "huggingface" and HF_API_TOKEN and visual_prompt:
        try:
            path = _hf_generate(visual_prompt, out_path, palette)
            if path:
                return path
        except Exception as e:
            print(f"[Image] HF failed: {e}, using local")

    # PIL local generation (always works)
    return _local_generate(section_index, section_title, section_content,
                           topic, total_sections, out_path, palette)


def _local_generate(idx: int, title: str, content: str, topic: str,
                    total: int, out_path: str, palette: dict) -> str:
    img  = _gradient_bg(palette)
    draw = ImageDraw.Draw(img)
    _add_geometric_decor(draw, palette, seed=idx)

    # Determine layout based on position
    if idx == 0:
        _render_intro_card(draw, palette, topic,
                           subtitle=_first_sentence(content))
    elif idx >= total - 1:
        _render_cta_card(draw, palette, "Thanks for watching!")
    else:
        # Alternate between bullet and quote layouts
        bullets = _extract_bullets(content)
        if len(bullets) >= 2:
            _render_bullet_card(draw, palette, title, bullets, idx)
        else:
            # Check for stat pattern (number-heavy content)
            stat = _extract_stat(content)
            if stat:
                _render_stat_card(draw, palette, stat[0], stat[1], title)
            else:
                _render_quote_card(draw, palette,
                                   _best_quote(content), context=title)

    # Progress bar (bottom)
    if total > 1:
        pw = int((idx / max(total-1, 1)) * VIDEO_W)
        draw.rectangle([0, VIDEO_H-6, pw, VIDEO_H], fill=palette["accent"])
        draw.rectangle([pw, VIDEO_H-6, VIDEO_W, VIDEO_H],
                       fill=tuple(int(c*0.2) for c in palette["accent"]))

    img.save(out_path, "JPEG", quality=92)
    return out_path


def _hf_generate(prompt: str, out_path: str, palette: dict) -> str:
    """Generate image via HuggingFace Inference API (free tier)."""
    import requests
    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
    enhanced = (f"cinematic 4K photo, {prompt}, professional lighting, "
                "ultra realistic, high quality, sharp focus")
    r = requests.post(API_URL, headers=headers,
                      json={"inputs": enhanced}, timeout=60)
    if r.status_code == 200:
        with open(out_path, "wb") as f:
            f.write(r.content)
        return out_path
    return ""


# ── Helpers ───────────────────────────────────────────────────────────────────
def _first_sentence(text: str) -> str:
    import re
    m = re.match(r"([^.!?]+[.!?])", text.strip())
    return m.group(1)[:80] if m else text[:80]

def _extract_bullets(text: str) -> list:
    import re
    # Look for numbered or bulleted lines
    items = re.findall(r'(?:^|\n)\s*(?:\d+[\.\)]\s*|[-•*]\s*)(.+)', text)
    if not items:
        # Split by sentences
        sentences = re.split(r'[.!?]+', text)
        items = [s.strip() for s in sentences if len(s.strip()) > 15]
    return [i[:100] for i in items[:6] if i.strip()]

def _extract_stat(text: str) -> tuple:
    import re
    m = re.search(r'(\d+(?:\.\d+)?(?:%|x|X|\s*billion|\s*million|\s*trillion)?)', text)
    if m and len(m.group(1)) >= 2:
        val = m.group(1)
        label = text[:60].replace(val, "").strip()
        return val, label
    return None

def _best_quote(text: str) -> str:
    import re
    sentences = re.split(r'[.!?]+', text)
    # Pick the longest meaningful sentence
    best = max((s.strip() for s in sentences if len(s.strip()) > 20),
               key=len, default=text[:120])
    return best[:150]


# ── Thumbnail generator ───────────────────────────────────────────────────────
def generate_thumbnail(topic: str, title: str, out_path: str) -> str:
    """Create YouTube-style thumbnail (1280x720)."""
    palette = get_palette(topic)
    W, H = VIDEO_W, VIDEO_H

    img  = _gradient_bg(palette)
    draw = ImageDraw.Draw(img)

    acc   = palette["accent"]
    acc2  = palette["accent2"]
    text_c = palette["text"]

    # Background glow circles
    for r, a_mult in [(350, 0.12), (250, 0.18), (150, 0.25)]:
        col = tuple(int(c * a_mult) for c in acc)
        draw.ellipse([W//2 - r, H//2 - r + 50,
                      W//2 + r, H//2 + r + 50], fill=col)

    # Decorative lines
    for i in range(8):
        x = i * (W // 8)
        col = tuple(int(c * 0.05) for c in acc)
        draw.line([(x, 0), (x, H)], fill=col, width=1)

    # Top label
    label = "AI Generated"
    lf = _font(24)
    lw = _text_w(draw, label, lf)
    draw.rectangle([0, 0, lw+24, 40], fill=acc2)
    draw.text((12, 8), label, font=lf, fill=(0,0,0))

    # Main title (large, bold, high contrast)
    title_lines = textwrap.wrap(title.upper(), 18)[:3]
    tf = _font(82, bold=True)
    ty = H//2 - len(title_lines) * 50 - 20
    for i, line in enumerate(title_lines):
        lw = _text_w(draw, line, tf)
        x  = (W - lw) // 2
        # Thick black shadow
        for dx, dy in [(-3,-3),(3,-3),(-3,3),(3,3),(0,4),(4,0)]:
            draw.text((x+dx, ty+dy), line, font=tf, fill=(0,0,0))
        # Gradient effect: first line in accent, rest in white
        col = acc if i == 0 else text_c
        draw.text((x, ty), line, font=tf, fill=col)
        ty += 96

    # Accent underline
    uw = min(600, _text_w(draw, title_lines[0] if title_lines else topic, tf))
    ux = (W - uw) // 2
    draw.rectangle([ux, ty, ux + uw, ty + 6], fill=acc2)

    # Bottom strip
    draw.rectangle([0, H-50, W, H], fill=tuple(int(c*0.3) for c in acc))
    strip_text = f"▶  {topic[:60]}"
    stf = _font(26)
    draw.text((20, H-38), strip_text, font=stf, fill=text_c)

    img.save(out_path, "JPEG", quality=95)
    return out_path
