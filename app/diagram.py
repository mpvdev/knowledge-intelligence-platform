"""Small, dependency-light PNG flow renderer for Slack."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def render_flow(nodes: str) -> BytesIO:
    labels = [item.strip() for item in nodes.split("\n↓\n") if item.strip()][:8]
    width, card_height, gap = 1200, 92, 34
    height = 80 + len(labels) * card_height + max(0, len(labels) - 1) * gap
    image = Image.new("RGB", (width, height), "#17191c")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=28)
    small = ImageFont.load_default(size=22)
    palette = ("#36c5f0", "#a78bfa", "#2eb67d", "#ecb22e", "#e01e5a")
    for index, label in enumerate(labels):
        top = 40 + index * (card_height + gap)
        color = palette[index % len(palette)]
        draw.rounded_rectangle(
            (40, top, width - 40, top + card_height),
            18,
            fill="#25282d",
            outline=color,
            width=3,
        )
        draw.ellipse((62, top + 25, 80, top + 43), fill=color)
        draw.text((102, top + 31), f"{index + 1:02d}", fill="#ffffff", font=small)
        draw.text((170, top + 30), label[:70], fill="#f4f4f5", font=font)
        if index < len(labels) - 1:
            center = top + card_height + gap // 2
            draw.line(
                (width // 2, center - 12, width // 2, center + 10),
                fill="#8b949e",
                width=4,
            )
            draw.polygon(
                (
                    (width // 2 - 8, center + 8),
                    (width // 2 + 8, center + 8),
                    (width // 2, center + 20),
                ),
                fill="#8b949e",
            )
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output
