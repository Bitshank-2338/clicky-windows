"""
Generate a Clicky-blue icon.ico for the PyInstaller build.

Produces assets/icon.ico with multiple sizes (16, 32, 48, 64, 128, 256) —
Windows picks the right size for taskbar, file explorer, and installer.

Run once before building:  python assets\make_icon.py
"""

from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent / "icon.ico"
BLUE = (0x33, 0x80, 0xFF, 255)     # Clicky cursor blue (#3380FF)


def make_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Soft outer glow (three concentric translucent circles)
    for r_mul, alpha in ((0.48, 55), (0.42, 110), (0.36, 170)):
        r = int(size * r_mul)
        cx = cy = size // 2
        d.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            fill=(BLUE[0], BLUE[1], BLUE[2], alpha),
        )

    # Solid blue triangle (the buddy), rotated -35°, scaled to fit
    tri_size = int(size * 0.55)
    tri = Image.new("RGBA", (tri_size * 2, tri_size * 2), (0, 0, 0, 0))
    td = ImageDraw.Draw(tri)
    # Equilateral triangle pointing up
    h = tri_size * 0.87
    cx = tri_size
    cy = tri_size
    td.polygon(
        [
            (cx, cy - h / 1.5),                 # top
            (cx - tri_size / 2, cy + h / 3),    # bottom-left
            (cx + tri_size / 2, cy + h / 3),    # bottom-right
        ],
        fill=BLUE,
    )
    tri = tri.rotate(35, resample=Image.BICUBIC)   # matches overlay.py
    # Paste centred
    img.paste(tri, ((size - tri.width) // 2, (size - tri.height) // 2), tri)
    return img


def main():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [make_frame(s) for s in sizes]
    # Pillow writes multi-resolution .ico when sizes= is passed
    frames[0].save(
        OUT,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"Wrote {OUT} ({len(sizes)} sizes)")


if __name__ == "__main__":
    main()
