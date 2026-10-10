"""Channel splash (заставка) image generation — Unical_Post style."""

from __future__ import annotations

import logging
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.cover_questions import COVER_QUESTIONS

logger = logging.getLogger(__name__)

SPLASH_DIR = Path(__file__).resolve().parents[2] / "media" / "splashes"
SPLASH_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1080, 1350


def _font_paths() -> list[Path]:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Georgia Italic.ttf"),
        Path("/System/Library/Fonts/Supplemental/Georgia.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ]
    return [p for p in candidates if p.exists()]


def _load_font(size: int, *, italic: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = _font_paths()
    # Prefer italic/serif for question, bold/sans for answer
    ordered = paths
    if italic:
        ordered = [p for p in paths if "Italic" in p.name or "Serif" in p.name] + paths
    else:
        ordered = [p for p in paths if "Sans" in p.name or "Arial" in p.name or "DejaVu" in p.name] + paths
    for path in ordered:
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_sparkles(draw: ImageDraw.ImageDraw, rng: random.Random) -> None:
    gold = (200, 167, 116, 255)
    soft = (232, 210, 160, 180)
    for _ in range(120):
        x = rng.randint(40, WIDTH - 40)
        # Keep center text area relatively clear
        if 220 < x < WIDTH - 220:
            continue
        y = rng.randint(80, HEIGHT - 80)
        r = rng.choice([1, 1, 2, 2, 3, 4])
        color = gold if rng.random() > 0.35 else soft
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        if r >= 3 and rng.random() > 0.5:
            arm = r + 2
            draw.line((x - arm, y, x + arm, y), fill=color, width=1)
            draw.line((x, y - arm, x, y + arm), fill=color, width=1)


def audience_language_for_profile(gender: str | None) -> str:
    """Female profile → Italian splash/caption for male readers; male → Russian."""
    if gender == "male":
        return "ru"
    return "it"


def pronoun_label(gender: str | None, language: str) -> str:
    if gender == "male":
        return "Он:" if language == "ru" else "Lui:"
    return "Lei:" if language == "it" else "Она:"


def build_splash_image(
    *,
    question: str,
    answer: str,
    pronoun: str,
    profile_id: int,
) -> Path:
    rng = random.Random(profile_id * 97 + len(answer))
    img = Image.new("RGBA", (WIDTH, HEIGHT), (8, 8, 8, 255))
    draw = ImageDraw.Draw(img)
    _draw_sparkles(draw, rng)

    q_font = _load_font(42, italic=True)
    a_font = _load_font(44, italic=False)
    p_font = _load_font(28, italic=False)

    max_w = WIDTH - 280
    q_lines = _wrap(draw, question, q_font, max_w)
    a_text = answer.strip().upper()
    a_lines = _wrap(draw, a_text, a_font, max_w)

    # Vertical layout: pronoun on top, question below it, answer last
    q_block_h = len(q_lines) * 54
    a_block_h = len(a_lines) * 56
    total_h = 48 + q_block_h + 36 + a_block_h
    y = (HEIGHT - total_h) // 2 - 40

    white = (245, 240, 232, 255)
    cream = (239, 228, 210, 255)

    pronoun_w = draw.textlength(pronoun, font=p_font)
    draw.text(((WIDTH - pronoun_w) / 2, y), pronoun, font=p_font, fill=(200, 167, 116, 255))
    y += 48

    for line in q_lines:
        tw = draw.textlength(line, font=q_font)
        draw.text(((WIDTH - tw) / 2, y), line, font=q_font, fill=cream)
        y += 54

    y += 36

    for line in a_lines:
        tw = draw.textlength(line, font=a_font)
        draw.text(((WIDTH - tw) / 2, y), line, font=a_font, fill=white)
        y += 56

    # Soft vignette edges
    vignette = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vignette)
    for i in range(80):
        alpha = int(90 * (1 - i / 80))
        vdraw.rectangle((i, i, WIDTH - 1 - i, HEIGHT - 1 - i), outline=(0, 0, 0, alpha))
    img = Image.alpha_composite(img, vignette)

    out = SPLASH_DIR / f"splash_{profile_id}.jpg"
    img.convert("RGB").save(out, quality=92)
    return out


def resolve_cover_texts(
    *,
    gender: str | None,
    cover_question_id: int | None,
    cover_answer: str,
    cover_answer_translated: str | None,
) -> tuple[str, str, str, str]:
    """Return (language, pronoun, question, answer) for splash."""
    language = audience_language_for_profile(gender)
    pronoun = pronoun_label(gender, language)
    qid = cover_question_id or 1
    question = COVER_QUESTIONS.get(qid, COVER_QUESTIONS[1]).get(language, "")
    answer = (cover_answer_translated or cover_answer or "").strip()
    if len(answer) > 70:
        answer = answer[:70]
    return language, pronoun, question, answer
