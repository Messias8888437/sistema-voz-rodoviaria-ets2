import math
import struct
import zlib
from pathlib import Path

SIZE = 256
SCALE = 4
LARGE_SIZE = SIZE * SCALE
ROOT = Path(__file__).resolve().parent


def blend(image: bytearray, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    if not (0 <= x < LARGE_SIZE and 0 <= y < LARGE_SIZE):
        return
    offset = (y * LARGE_SIZE + x) * 4
    alpha = color[3]
    if alpha == 255:
        image[offset:offset + 4] = bytes(color)
        return
    old_alpha = image[offset + 3]
    out_alpha = alpha + old_alpha * (255 - alpha) // 255
    if not out_alpha:
        return
    for channel in range(3):
        image[offset + channel] = (
            color[channel] * alpha
            + image[offset + channel] * old_alpha * (255 - alpha) // 255
        ) // out_alpha
    image[offset + 3] = out_alpha


def rounded_rect(
    image: bytearray,
    bounds: tuple[float, float, float, float],
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = bounds
    left_px = max(0, int(left * SCALE))
    right_px = min(LARGE_SIZE, math.ceil(right * SCALE))
    top_px = max(0, int(top * SCALE))
    bottom_px = min(LARGE_SIZE, math.ceil(bottom * SCALE))
    radius_sq = (radius * SCALE) ** 2
    for y in range(top_px, bottom_px):
        for x in range(left_px, right_px):
            nearest_x = min(max(x + 0.5, (left + radius) * SCALE), (right - radius) * SCALE)
            nearest_y = min(max(y + 0.5, (top + radius) * SCALE), (bottom - radius) * SCALE)
            if (x + 0.5 - nearest_x) ** 2 + (y + 0.5 - nearest_y) ** 2 <= radius_sq:
                blend(image, x, y, color)


def circle(
    image: bytearray,
    center: tuple[float, float],
    radius: float,
    color: tuple[int, int, int, int],
) -> None:
    cx, cy = center
    cx *= SCALE
    cy *= SCALE
    radius *= SCALE
    for y in range(max(0, int(cy - radius)), min(LARGE_SIZE, math.ceil(cy + radius))):
        for x in range(max(0, int(cx - radius)), min(LARGE_SIZE, math.ceil(cx + radius))):
            if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 <= radius ** 2:
                blend(image, x, y, color)


def line(
    image: bytearray,
    start: tuple[float, float],
    end: tuple[float, float],
    width: float,
    color: tuple[int, int, int, int],
) -> None:
    ax, ay = start
    bx, by = end
    ax *= SCALE
    ay *= SCALE
    bx *= SCALE
    by *= SCALE
    radius = width * SCALE / 2
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    for y in range(max(0, int(min(ay, by) - radius)), min(LARGE_SIZE, math.ceil(max(ay, by) + radius))):
        for x in range(max(0, int(min(ax, bx) - radius)), min(LARGE_SIZE, math.ceil(max(ax, bx) + radius))):
            fraction = 0 if not length_sq else max(0, min(1, ((x + 0.5 - ax) * dx + (y + 0.5 - ay) * dy) / length_sq))
            nearest_x = ax + fraction * dx
            nearest_y = ay + fraction * dy
            if (x + 0.5 - nearest_x) ** 2 + (y + 0.5 - nearest_y) ** 2 <= radius ** 2:
                blend(image, x, y, color)


def render() -> bytearray:
    image = bytearray(LARGE_SIZE * LARGE_SIZE * 4)
    colors = ((8, 24, 48), (9, 91, 128))
    for y in range(LARGE_SIZE):
        mix = y / (LARGE_SIZE - 1)
        row_color = tuple(round(colors[0][i] * (1 - mix) + colors[1][i] * mix) for i in range(3))
        for x in range(LARGE_SIZE):
            offset = (y * LARGE_SIZE + x) * 4
            image[offset:offset + 4] = bytes((*row_color, 255))

    rounded_rect(image, (0, 0, SIZE, SIZE), 48, (0, 0, 0, 0))
    for y in range(LARGE_SIZE):
        for x in range(LARGE_SIZE):
            nearest_x = min(max(x + 0.5, 48 * SCALE), (SIZE - 48) * SCALE)
            nearest_y = min(max(y + 0.5, 48 * SCALE), (SIZE - 48) * SCALE)
            if (x + 0.5 - nearest_x) ** 2 + (y + 0.5 - nearest_y) ** 2 > (48 * SCALE) ** 2:
                image[(y * LARGE_SIZE + x) * 4 + 3] = 0

    gold = (255, 197, 82, 255)
    line(image, (43, 192), (82, 192), 8, gold)
    line(image, (82, 192), (104, 170), 8, gold)
    line(image, (104, 170), (150, 170), 8, gold)
    line(image, (150, 170), (177, 198), 8, gold)
    line(image, (177, 198), (211, 198), 8, gold)
    for point in ((43, 192), (211, 198)):
        circle(image, point, 9, gold)

    rounded_rect(image, (63, 53, 190, 163), 22, (244, 250, 255, 255))
    rounded_rect(image, (73, 64, 180, 118), 12, (13, 52, 77, 255))
    rounded_rect(image, (82, 73, 105, 107), 6, (92, 207, 228, 255))
    rounded_rect(image, (113, 73, 136, 107), 6, (92, 207, 228, 255))
    rounded_rect(image, (144, 73, 170, 107), 6, (92, 207, 228, 255))
    rounded_rect(image, (75, 126, 179, 143), 6, (25, 117, 153, 255))
    circle(image, (91, 158), 12, (8, 24, 48, 255))
    circle(image, (91, 158), 5, (177, 218, 232, 255))
    circle(image, (162, 158), 12, (8, 24, 48, 255))
    circle(image, (162, 158), 5, (177, 218, 232, 255))
    return image


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(image: bytearray, size: int) -> bytes:
    pixels = bytearray()
    step = LARGE_SIZE // size
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            red = green = blue = alpha = 0
            for sy in range(step):
                for sx in range(step):
                    offset = (((y * step + sy) * LARGE_SIZE) + x * step + sx) * 4
                    red += image[offset]
                    green += image[offset + 1]
                    blue += image[offset + 2]
                    alpha += image[offset + 3]
            samples = step * step
            pixels.extend((red // samples, green // samples, blue // samples, alpha // samples))
    header = struct.pack(">2I5B", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header) + png_chunk(b"IDAT", zlib.compress(pixels, 9)) + png_chunk(b"IEND", b"")


def main() -> None:
    image = render()
    sizes = (16, 24, 32, 48, 64, 128, 256)
    entries = [encode_png(image, size) for size in sizes]
    directory = bytearray(struct.pack("<HHH", 0, 1, len(entries)))
    offset = 6 + 16 * len(entries)
    for size, data in zip(sizes, entries):
        directory.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (ROOT / "RodoviariaETS2.ico").write_bytes(directory + b"".join(entries))
    (ROOT / "RodoviariaETS2.png").write_bytes(encode_png(image, SIZE))


if __name__ == "__main__":
    main()
