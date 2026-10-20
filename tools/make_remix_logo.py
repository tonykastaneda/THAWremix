"""Composite the original THUG2 Remix tape onto the THAW logo."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


downloads = Path.home() / "Downloads"
source = Image.open(downloads / "THUG2_remix_logo.webp").convert("RGBA")
target = Image.open(downloads / "Tony_Hawk's_American_Wasteland_-_logo.png").convert("RGBA")

# Follow the outer edge of the silver tape, retaining its original lettering.
left, top, right, bottom = 128, 122, 349, 187
tape = source.crop((left, top, right, bottom))
mask = Image.new("L", tape.size)
draw = ImageDraw.Draw(mask)
draw.polygon(
    [(0, 2), (10, 0), (210, 0), (217, 1), (219, 60), (211, 63), (15, 64), (8, 62)],
    fill=255,
)
mask = mask.filter(ImageFilter.GaussianBlur(0.35))
tape.putalpha(mask)

width = 650
tape = tape.resize((width, round(width * tape.height / tape.width)), Image.Resampling.LANCZOS)
canvas = Image.new("RGBA", (target.width, 860))
canvas.alpha_composite(target, (0, 0))
canvas.alpha_composite(tape, ((target.width - tape.width) // 2, 650))

output = Path(__file__).resolve().parents[1] / "work" / "THAW_American_Wasteland_Remix.png"
output.parent.mkdir(parents=True, exist_ok=True)
canvas.save(output, optimize=True)
print(output)
