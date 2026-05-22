"""One-time script: generates ConstraintLens button PNGs for the Fusion toolbar.

Run from the project root:
    python generate_icons.py

Writes 16x16.png, 32x32.png, 64x64.png to
ConstraintLens/Resources/ConstraintLens/ using only stdlib (struct + zlib).
"""
import math, struct, zlib, os


def _make_png(pixels, size):
    def crc32(data): return struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF)
    def chunk(tag, data): return struct.pack(">I", len(data)) + tag + data + crc32(tag + data)
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixels[y * size + x]) for x in range(size))
        for y in range(size)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _draw_icon(size):
    """Magnifying-glass icon: blue ring + inner crosshair + diagonal handle."""
    RING    = (72, 149, 239, 255)   # #4895EF
    CROSS   = (200, 225, 255, 200)  # pale blue-white crosshair
    HANDLE  = (72, 149, 239, 255)
    NONE    = (0, 0, 0, 0)

    s        = size / 16.0
    cx = cy  = 7.0 * s      # lens centre, offset up-left so handle fits
    outer_r  = 5.5 * s
    inner_r  = 3.5 * s
    cross_w  = 0.65 * s
    h_range  = outer_r + 5.5 * s   # handle max reach from centre
    h_width  = 1.4 * s             # half-width of handle (|dx-dy| threshold)

    pixels = []
    for y in range(size):
        for x in range(size):
            dx = x + 0.5 - cx
            dy = y + 0.5 - cy
            dist = math.sqrt(dx * dx + dy * dy)

            if inner_r < dist <= outer_r:
                pixels.append(RING)
            elif dist <= inner_r:
                pixels.append(CROSS if (abs(dx) <= cross_w or abs(dy) <= cross_w) else NONE)
            elif dx > 0 and dy > 0 and abs(dx - dy) < h_width and dist <= h_range:
                pixels.append(HANDLE)
            else:
                pixels.append(NONE)

    return pixels


def main():
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ConstraintLens", "Resources", "ConstraintLens",
    )
    os.makedirs(out_dir, exist_ok=True)
    for sz in (16, 32, 64):
        path = os.path.join(out_dir, f"{sz}x{sz}.png")
        with open(path, "wb") as f:
            f.write(_make_png(_draw_icon(sz), sz))
        print(f"  {sz}x{sz} -> {path}")
    print("Done.")


if __name__ == "__main__":
    main()
