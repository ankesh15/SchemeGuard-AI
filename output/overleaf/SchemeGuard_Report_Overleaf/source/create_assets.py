#!/usr/bin/env python3
"""Create the project-specific raster artwork used by the Overleaf bundle.

Run from any directory with Pillow installed:
    python3 source/create_assets.py
"""

from __future__ import annotations

from pathlib import Path
import shutil
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "images"
GREEN = "#176B4D"
GREEN_DARK = "#104C37"
PALE = "#E9F3EE"
PALE_BLUE = "#EFF5F7"
INK = "#1E3028"
GRAY = "#56635C"
LINE = "#D6E3DB"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrapped(draw: ImageDraw.ImageDraw, text: str, max_width: int, face) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textbbox((0, 0), candidate, font=face)[2] > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def text_block(draw, xy, text, max_width, face, fill=GRAY, gap=8):
    x, y = xy
    for line in wrapped(draw, text, max_width, face):
        draw.text((x, y), line, font=face, fill=fill)
        y += face.size + gap
    return y


def box(draw, rect, title, detail, *, accent=GREEN, fill=WHITE, title_size=28, body_size=21):
    draw.rounded_rectangle(rect, radius=22, fill=fill, outline=LINE, width=3)
    left, top, right, bottom = rect
    draw.rounded_rectangle((left, top, left + 13, bottom), radius=6, fill=accent)
    draw.text((left + 34, top + 25), title, font=font(title_size, True), fill=INK)
    text_block(draw, (left + 34, top + 74), detail, right - left - 66, font(body_size), fill=GRAY, gap=7)


def arrow(draw, start, end, color=GREEN, width=6):
    draw.line((start, end), fill=color, width=width)
    import math

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 22
    wing = 0.55
    p1 = (end[0] - length * math.cos(angle - wing), end[1] - length * math.sin(angle - wing))
    p2 = (end[0] - length * math.cos(angle + wing), end[1] - length * math.sin(angle + wing))
    draw.polygon((end, p1, p2), fill=color)


def make_logo() -> None:
    image = Image.new("RGBA", (1100, 300), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    shield = [(52, 44), (132, 18), (212, 44), (212, 165), (132, 218), (52, 165)]
    draw.polygon(shield, fill=PALE, outline=GREEN)
    draw.line((88, 119, 121, 151, 178, 87), fill=GREEN, width=13, joint="curve")
    draw.text((255, 48), "SchemeGuard", font=font(92, True), fill=GREEN_DARK)
    draw.text((260, 166), "Evidence-led scheme discovery", font=font(31), fill=GRAY)
    image.save(ASSETS / "SchemeGuard_logo.png")
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="300" viewBox="0 0 1100 300">
<path d="M52 44 132 18 212 44v121l-80 53-80-53z" fill="#E9F3EE" stroke="#176B4D" stroke-width="5"/>
<path d="m88 119 33 32 57-64" fill="none" stroke="#176B4D" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>
<text x="255" y="126" font-family="DejaVu Sans,Arial,sans-serif" font-size="92" font-weight="700" fill="#104C37">SchemeGuard</text>
<text x="260" y="205" font-family="DejaVu Sans,Arial,sans-serif" font-size="31" fill="#56635C">Evidence-led scheme discovery</text></svg>'''
    (ASSETS / "SchemeGuard_logo.svg").write_text(svg, encoding="utf-8")


def make_architecture() -> None:
    image = Image.new("RGB", (1800, 980), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((70, 44), "SchemeGuard system architecture", font=font(42, True), fill=GREEN_DARK)
    box(draw, (75, 175, 530, 415), "People and browser", "Citizens, guests and administrators use responsive web workspaces.", fill=PALE_BLUE)
    box(draw, (665, 175, 1120, 415), "Next.js frontend", "Profile-first discovery, supported assessments and protected review.", fill=PALE)
    box(draw, (1255, 175, 1725, 415), "FastAPI modular monolith", "Versioned APIs, recommendations, eligibility, document review and monitoring.", fill=PALE_BLUE)
    arrow(draw, (530, 295), (665, 295))
    arrow(draw, (1120, 295), (1255, 295))
    box(draw, (245, 610, 710, 855), "PostgreSQL", "Schemes, evidence, immutable policy versions, assessments and audit history.")
    box(draw, (790, 610, 1255, 855), "Redis and Celery", "Internal task delivery for document processing, monitoring and reassessment.", fill=PALE)
    box(draw, (1335, 610, 1785, 855), "Persistent documents", "Checksummed source PDFs and page-aware extracted content.", fill=PALE_BLUE)
    arrow(draw, (1430, 415), (575, 610))
    arrow(draw, (1485, 415), (1020, 610))
    arrow(draw, (1570, 415), (1560, 610))
    image.save(ASSETS / "schemeguard-architecture.png")


def make_workflow(filename: str, heading: str, steps: list[tuple[str, str]], *, width=1850):
    margin, gap = 45, 28
    count = len(steps)
    box_width = (width - 2 * margin - gap * (count - 1)) // count
    height = 650
    image = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((margin, 45), heading, font=font(39, True), fill=GREEN_DARK)
    top, bottom = 190, 535
    for index, (title, detail) in enumerate(steps):
        left = margin + index * (box_width + gap)
        fill = PALE if index % 2 == 0 else PALE_BLUE
        box(draw, (left, top, left + box_width, bottom), title, detail, fill=fill, title_size=25, body_size=20)
        if index < count - 1:
            arrow(draw, (left + box_width + 3, (top + bottom) // 2), (left + box_width + gap - 3, (top + bottom) // 2))
    image.save(ASSETS / filename)


def make_journey() -> None:
    width, height = 1500, 1220
    image = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((90, 45), "A profile-first citizen journey", font=font(42, True), fill=GREEN_DARK)
    steps = [
        ("1  Tell us about yourself", "Share only the optional profile details and interests that help discovery."),
        ("2  Discover relevant schemes", "The catalog is ranked by transparent category and profile matches."),
        ("3  Explore scheme details", "Review source links, verified metadata and assessment support."),
        ("4  Check supported requirements", "A strict result uses an applicable, human-approved rule version."),
        ("5  Understand the report", "Read evidence references, missing information and the informational notice."),
    ]
    y = 155
    for index, (title, detail) in enumerate(steps):
        box(draw, (145, y, 1355, y + 170), title, detail, fill=PALE if index % 2 == 0 else PALE_BLUE, title_size=29, body_size=23)
        if index < len(steps) - 1:
            arrow(draw, (750, y + 174), (750, y + 208), width=5)
        y += 205
    image.save(ASSETS / "profile-first-journey.png")


def make_mobile_card() -> None:
    width, height = 780, 1010
    image = Image.new("RGB", (width, height), "#F7FAF8")
    draw = ImageDraw.Draw(image)
    draw.text((52, 36), "Illustrative mobile recommendation card", font=font(30, True), fill=GREEN_DARK)
    draw.rounded_rectangle((34, 110, 746, 978), radius=30, fill=WHITE, outline=LINE, width=3)
    draw.rounded_rectangle((66, 145, 282, 198), radius=24, fill=PALE)
    draw.text((88, 158), "Scholarships", font=font(21, True), fill=GREEN_DARK)
    draw.rounded_rectangle((472, 145, 704, 198), radius=24, fill="#EAF4E5")
    draw.text((495, 158), "Highly relevant", font=font(19, True), fill=GREEN_DARK)
    draw.text((68, 238), "Ishan Uday Special", font=font(32, True), fill=INK)
    draw.text((68, 282), "Scholarship", font=font(32, True), fill=INK)
    y = text_block(draw, (68, 355), "UGC scholarship assistance to expand access to undergraduate education for students from India's North Eastern Region.", 620, font(24), fill=GRAY, gap=9)
    draw.line((68, y + 12, 710, y + 12), fill=LINE, width=2)
    y += 45
    draw.text((68, y), "Why this scheme?", font=font(24, True), fill=INK)
    y += 54
    reasons = [
        "Matches your interest in scholarship",
        "Related to your student status",
        "Verified coverage includes your state",
        "Detailed criteria need further review",
    ]
    for reason in reasons:
        draw.ellipse((72, y + 5, 94, y + 27), outline=GREEN, width=3)
        draw.line((78, y + 16, 84, y + 22, 90, y + 10), fill=GREEN, width=3)
        y = text_block(draw, (112, y), reason, 575, font(22), fill=INK, gap=7) + 18
    draw.rounded_rectangle((68, 850, 710, 922), radius=15, outline=GREEN, width=2)
    draw.text((100, 872), "View details", font=font(24, True), fill=GREEN_DARK)
    draw.text((580, 872), "→", font=font(28, True), fill=GREEN_DARK)
    image.save(ASSETS / "recommendation-card-mobile.png")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    make_logo()
    make_architecture()
    make_workflow(
        "document-processing-workflow.png",
        "Document-to-policy workflow with a human publication gate",
        [
            ("Official source", "Approved URL or administrator-uploaded PDF; validate bytes and provenance."),
            ("Page-aware extraction", "PyMuPDF preserves page numbers, text blocks and extraction issues."),
            ("Candidate rules", "Structured output is typed, bounded and checked against located evidence."),
            ("Human review", "A reviewer inspects the exact saved proposal; uncertain clauses stay pending."),
            ("Rule publication", "Only approved, evidenced rules become executable policy."),
        ],
    )
    make_workflow(
        "policy-monitoring-workflow.png",
        "Monitoring records changes; reviewers determine policy meaning",
        [
            ("Opt-in schedule", "Only explicitly selected sources are checked."),
            ("Safe fetch", "Timeouts, redirects, validators and SHA-256 protect retrieval."),
            ("New version", "Changed bytes are preserved; unchanged documents are skipped."),
            ("Rule comparison", "Old approved rules are compared with sourced candidates."),
            ("Review and replay", "Approval appends a version and starts scoped reassessment."),
        ],
    )
    make_journey()
    make_mobile_card()
    shutil.copyfile(ASSETS / "document-processing-workflow.png", ROOT / "pic1.png")
    print(f"Created SchemeGuard report artwork in {ASSETS}")


if __name__ == "__main__":
    main()
