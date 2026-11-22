"""Generate an original static height-field texture (decorative, not geographic data).

Run `python frontend/scripts/generate-contours.py` from the repository root.
Marching squares joins shared edges before simplifying to smooth SVG paths.
"""
import math
from pathlib import Path

W, H, STEP = 1600, 1100, 10


def noise(x, y):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    def sample(a, b):
        n = (a * 374761393 + b * 668265263 + 73493) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return (n ^ (n >> 16)) / 0xFFFFFFFF * 2 - 1
    a, b, c, d = sample(ix, iy), sample(ix + 1, iy), sample(ix, iy + 1), sample(ix + 1, iy + 1)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def height(x, y):
    u, v = x / W, y / H
    u += .075 * noise(u * 3 + 4, v * 3 - 5)
    v += .09 * noise(u * 3 - 8, v * 3 + 2)
    slope = .60 * u + .10 * v
    ridges = .20 * math.sin(5.6 * u + 2.2 * v + .5 * math.sin(v * 5))
    ridges += .12 * math.sin(10.5 * u - 4.2 * v + .6 * math.cos(v * 3))
    detail = .075 * noise(u * 5, v * 5) + .025 * noise(u * 11 + 7, v * 11) + .008 * noise(u * 23, v * 23)
    summit = .14 * math.exp(-(((u - .85) / .18) ** 2 + ((v - .03) / .24) ** 2))
    valley = -.12 * math.exp(-(((u - 1.06) / .20) ** 2 + ((v - .74) / .19) ** 2))
    return slope + ridges + detail + summit + valley


def simplify(points, tolerance=1.25):
    if len(points) < 3: return points
    ax, ay = points[0]
    bx, by = points[-1]
    length = math.hypot(bx - ax, by - ay)
    distances = [abs((bx - ax) * (ay - y) - (ax - x) * (by - ay)) / length if length else math.hypot(x - ax, y - ay) for x, y in points[1:-1]]
    if max(distances, default=0) <= tolerance: return [points[0], points[-1]]
    index = distances.index(max(distances)) + 1
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def curve(points):
    if len(points) < 3: return ''
    result = [f'M{points[0][0]:.1f} {points[0][1]:.1f}']
    for i in range(1, len(points) - 1):
        x, y = points[i]
        nx, ny = points[i + 1]
        result.append(f'Q{x:.1f} {y:.1f} {(x + nx) / 2:.1f} {(y + ny) / 2:.1f}')
    result.append(f'L{points[-1][0]:.1f} {points[-1][1]:.1f}')
    return ''.join(result)


def build():
    nx, ny = W // STEP, H // STEP
    grid = [[height(x * STEP, y * STEP) for x in range(nx + 1)] for y in range(ny + 1)]
    low, high = min(map(min, grid)), max(map(max, grid))
    lines = []
    pairs = {1: [(3, 0)], 2: [(0, 1)], 3: [(3, 1)], 4: [(1, 2)], 6: [(0, 2)], 7: [(3, 2)], 8: [(2, 3)], 9: [(0, 2)], 11: [(1, 2)], 12: [(3, 1)], 13: [(0, 1)], 14: [(3, 0)]}
    for layer in range(1, 34):
        threshold = low + (high - low) * layer / 34
        coordinates, neighbors = {}, {}
        for y in range(ny):
            for x in range(nx):
                values = [grid[y][x], grid[y][x + 1], grid[y + 1][x + 1], grid[y + 1][x]]
                mask = sum(1 << i for i, value in enumerate(values) if value >= threshold)
                if mask in (0, 15): continue
                segments = pairs.get(mask)
                if segments is None:
                    center_high = sum(values) / 4 >= threshold
                    segments = [(0, 1), (2, 3)] if (mask == 5 and center_high) or (mask == 10 and not center_high) else [(3, 0), (1, 2)]
                vertices = [(x * STEP, y * STEP), ((x + 1) * STEP, y * STEP), ((x + 1) * STEP, (y + 1) * STEP), (x * STEP, (y + 1) * STEP)]
                def edge(e):
                    key = [('h', x, y), ('v', x + 1, y), ('h', x, y + 1), ('v', x, y)][e]
                    if key not in coordinates:
                        a, b = e, (e + 1) % 4
                        weight = (threshold - values[a]) / (values[b] - values[a])
                        coordinates[key] = tuple(vertices[a][axis] + (vertices[b][axis] - vertices[a][axis]) * weight for axis in (0, 1))
                    return key
                for a, b in segments:
                    ka, kb = edge(a), edge(b)
                    neighbors.setdefault(ka, []).append(kb)
                    neighbors.setdefault(kb, []).append(ka)
        visited = set()
        endpoints = [key for key, links in neighbors.items() if len(links) == 1]
        for first in endpoints + list(neighbors):
            if first in visited: continue
            points, previous, current = [], None, first
            while current not in visited:
                visited.add(current)
                points.append(coordinates[current])
                following = [key for key in neighbors[current] if key != previous]
                if not following: break
                previous, current = current, following[0]
            if current == first: points.append(points[0])
            if len(points) < 10: continue
            path = curve(simplify(points))
            if path: lines.append((layer, path))
    target = Path(__file__).resolve().parents[1] / 'src/assets/terrain-contours.svg'
    paths = ''.join(f'<path d="{path}" stroke-width="{1.15 if layer % 5 == 0 else .7}" opacity="{.85 if layer % 5 == 0 else .55}"/>' for layer, path in lines)
    target.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" fill="none"><g stroke="white" stroke-linecap="round" stroke-linejoin="round">{paths}</g></svg>\n', encoding='utf-8')
    print(f'{len(lines)} joined contour paths; {target.stat().st_size} bytes')


if __name__ == '__main__': build()
