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


def ellipse(
    image: bytearray,
    bounds: tuple[float, float, float, float],
    color: tuple[int, int, int, int],
) -> None:
    left, top, right, bottom = bounds
    center_x = (left + right) * SCALE / 2
    center_y = (top + bottom) * SCALE / 2
    radius_x = (right - left) * SCALE / 2
    radius_y = (bottom - top) * SCALE / 2
    for y in range(max(0, int(top * SCALE)), min(LARGE_SIZE, math.ceil(bottom * SCALE))):
        for x in range(max(0, int(left * SCALE)), min(LARGE_SIZE, math.ceil(right * SCALE))):
            if ((x + 0.5 - center_x) / radius_x) ** 2 + ((y + 0.5 - center_y) / radius_y) ** 2 <= 1:
                blend(image, x, y, color)


def polygon(
    image: bytearray,
    points: tuple[tuple[float, float], ...],
    color: tuple[int, int, int, int],
) -> None:
    scaled = tuple((x * SCALE, y * SCALE) for x, y in points)
    top = max(0, int(min(y for _, y in scaled)))
    bottom = min(LARGE_SIZE, math.ceil(max(y for _, y in scaled)))
    for y in range(top, bottom):
        scan_y = y + 0.5
        intersections = []
        for index, (x1, y1) in enumerate(scaled):
            x2, y2 = scaled[(index + 1) % len(scaled)]
            if (y1 <= scan_y < y2) or (y2 <= scan_y < y1):
                intersections.append(x1 + (scan_y - y1) * (x2 - x1) / (y2 - y1))
        intersections.sort()
        for index in range(0, len(intersections), 2):
            left = max(0, math.ceil(intersections[index] - 0.5))
            right = min(LARGE_SIZE, math.ceil(intersections[index + 1] - 0.5))
            for x in range(left, right):
                blend(image, x, y, color)


def polygon_gradient(
    image: bytearray,
    points: tuple[tuple[float, float], ...],
    left_color: tuple[int, int, int, int],
    right_color: tuple[int, int, int, int],
) -> None:
    scaled = tuple((x * SCALE, y * SCALE) for x, y in points)
    min_x = min(x for x, _ in scaled)
    max_x = max(x for x, _ in scaled)
    top = max(0, int(min(y for _, y in scaled)))
    bottom = min(LARGE_SIZE, math.ceil(max(y for _, y in scaled)))
    for y in range(top, bottom):
        scan_y = y + 0.5
        intersections = []
        for index, (x1, y1) in enumerate(scaled):
            x2, y2 = scaled[(index + 1) % len(scaled)]
            if (y1 <= scan_y < y2) or (y2 <= scan_y < y1):
                intersections.append(x1 + (scan_y - y1) * (x2 - x1) / (y2 - y1))
        intersections.sort()
        for index in range(0, len(intersections), 2):
            start = max(0, math.ceil(intersections[index] - 0.5))
            end = min(LARGE_SIZE, math.ceil(intersections[index + 1] - 0.5))
            for x in range(start, end):
                mix = min(1.0, max(0.0, (x - min_x) / (max_x - min_x)))
                color = tuple(
                    round(left_color[channel] * (1 - mix) + right_color[channel] * mix)
                    for channel in range(4)
                )
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
    colors = ((6, 18, 38), (11, 48, 77))
    for y in range(LARGE_SIZE):
        mix = y / (LARGE_SIZE - 1)
        row_color = tuple(round(colors[0][i] * (1 - mix) + colors[1][i] * mix) for i in range(3))
        for x in range(LARGE_SIZE):
            glow = max(0, 1 - math.sqrt(((x - LARGE_SIZE * 0.46) / (LARGE_SIZE * 0.72)) ** 2 + ((y - LARGE_SIZE * 0.40) / (LARGE_SIZE * 0.8)) ** 2))
            offset = (y * LARGE_SIZE + x) * 4
            image[offset:offset + 4] = bytes((
                min(255, round(row_color[0] + 8 * glow)),
                min(255, round(row_color[1] + 43 * glow)),
                min(255, round(row_color[2] + 66 * glow)),
                255,
            ))

    rounded_rect(image, (0, 0, SIZE, SIZE), 48, (0, 0, 0, 0))
    for y in range(LARGE_SIZE):
        for x in range(LARGE_SIZE):
            nearest_x = min(max(x + 0.5, 48 * SCALE), (SIZE - 48) * SCALE)
            nearest_y = min(max(y + 0.5, 48 * SCALE), (SIZE - 48) * SCALE)
            if (x + 0.5 - nearest_x) ** 2 + (y + 0.5 - nearest_y) ** 2 > (48 * SCALE) ** 2:
                image[(y * LARGE_SIZE + x) * 4 + 3] = 0

    ellipse(image, (35, 183, 217, 215), (0, 0, 0, 105))
    line(image, (38, 207), (83, 207), 3, (85, 111, 130, 255))
    line(image, (173, 207), (217, 207), 3, (85, 111, 130, 255))
    line(image, (89, 207), (106, 192), 3, (255, 198, 83, 255))
    line(image, (106, 192), (148, 192), 3, (255, 198, 83, 255))
    line(image, (148, 192), (166, 207), 3, (255, 198, 83, 255))

    polygon(image, ((64, 76), (150, 64), (199, 82), (199, 160), (156, 177), (71, 165)), (8, 31, 51, 255))
    polygon_gradient(
        image, ((69, 71), (148, 59), (195, 77), (153, 87), (72, 99)),
        (251, 253, 250, 255), (188, 219, 228, 255),
    )
    polygon_gradient(
        image, ((72, 99), (153, 87), (153, 169), (72, 159)),
        (238, 246, 245, 255), (178, 210, 221, 255),
    )
    polygon_gradient(
        image, ((153, 87), (195, 77), (195, 154), (153, 169)),
        (189, 220, 228, 255), (104, 151, 171, 255),
    )

    polygon_gradient(
        image, ((80, 78), (143, 69), (146, 104), (80, 113)),
        (12, 41, 63, 255), (3, 21, 39, 255),
    )
    polygon(image, ((84, 81), (139, 73), (141, 78), (84, 87)), (151, 224, 235, 230))
    polygon(image, ((87, 90), (94, 89), (96, 104), (88, 105)), (203, 236, 239, 105))
    line(image, (87, 107), (137, 100), 2, (27, 105, 139, 255))
    for top, bottom in ((90, 111), (116, 137)):
        polygon_gradient(
            image,
            ((158, top + 1), (187, top - 6), (187, bottom - 7), (158, bottom)),
            (15, 58, 78, 255), (4, 28, 48, 255),
        )
        line(image, (162, top + 4), (181, top), 2, (146, 224, 235, 230))
    line(image, (151, 88), (151, 164), 2, (245, 250, 246, 220))

    polygon(image, ((72, 126), (153, 117), (195, 105), (195, 116), (153, 131), (72, 139)), (8, 104, 143, 255))
    line(image, (78, 143), (148, 135), 2, (255, 200, 89, 255))
    line(image, (160, 130), (190, 120), 2, (255, 200, 89, 255))
    rounded_rect(image, (78, 148, 103, 154), 2, (14, 42, 59, 255))
    for x in (82, 88, 94, 100):
        line(image, (x, 149), (x, 153), 1, (110, 169, 188, 255))

    rounded_rect(image, (76, 158, 94, 165), 3, (255, 228, 141, 255))
    rounded_rect(image, (139, 150, 153, 156), 2, (255, 225, 141, 255))
    circle(image, (91, 171), 12, (7, 18, 32, 255))
    circle(image, (91, 171), 7, (104, 133, 149, 255))
    circle(image, (91, 171), 3, (14, 39, 57, 255))
    circle(image, (170, 165), 12, (7, 18, 32, 255))
    circle(image, (170, 165), 7, (104, 133, 149, 255))
    circle(image, (170, 165), 3, (14, 39, 57, 255))

    line(image, (81, 64), (146, 54), 2, (255, 255, 255, 225))
    line(image, (78, 67), (142, 57), 1, (43, 101, 130, 255))
    circle(image, (43, 207), 4, (255, 198, 83, 255))
    circle(image, (212, 207), 4, (255, 198, 83, 255))
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
