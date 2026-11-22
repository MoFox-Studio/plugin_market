import { SHEET_HEIGHT, WORLD_WIDTH } from './useSurveyWorld';

const STEP = 16;
const INTERVAL = 0.035;
const COLUMNS = WORLD_WIDTH / STEP;
const ROWS = SHEET_HEIGHT / STEP;
type Point = [number, number];
interface Vertex { point: Point; neighbors: number[] }
interface Contours { minor: string; major: string }
const cache = new Map<number, Contours>();

function lattice(x: number, y: number) {
  let n = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + 73493) | 0;
  n = Math.imul(n ^ (n >>> 13), 1274126177);
  return ((n ^ (n >>> 16)) >>> 0) / 0xffffffff * 2 - 1;
}
function noise(x: number, y: number) {
  const ix = Math.floor(x), iy = Math.floor(y);
  const fx = x - ix, fy = y - iy;
  const u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy);
  const top = lattice(ix, iy) * (1 - u) + lattice(ix + 1, iy) * u;
  const bottom = lattice(ix, iy + 1) * (1 - u) + lattice(ix + 1, iy + 1) * u;
  return top * (1 - v) + bottom * v;
}
function elevation(x: number, y: number) {
  let u = x / WORLD_WIDTH, v = y / 1100;
  u += 0.075 * noise(u * 3 + 4, v * 3 - 5);
  v += 0.09 * noise(u * 3 - 8, v * 3 + 2);
  const ridge = 0.2 * Math.sin(5.6 * u + 2.2 * v + 0.5 * Math.sin(v * 5))
    + 0.12 * Math.sin(10.5 * u - 4.2 * v + 0.6 * Math.cos(v * 3));
  return 0.6 * u + 0.1 * v + ridge + 0.12 * noise(u * 1.4, v * 1.3)
    + 0.075 * noise(u * 5, v * 5) + 0.025 * noise(u * 11 + 7, v * 11)
    + 0.008 * noise(u * 23, v * 23);
}

// Each cell edge has a unique key shared by its adjacent cell.
const pairs: Record<number, number[]> = {
  1: [3, 0], 2: [0, 1], 3: [3, 1], 4: [1, 2], 6: [0, 2], 7: [3, 2],
  8: [2, 3], 9: [0, 2], 11: [1, 2], 12: [3, 1], 13: [0, 1], 14: [3, 0],
};
function paths(graph: Map<number, Vertex>) {
  const visited = new Set<number>();
  const endpoints = Array.from(graph.keys()).filter(key => graph.get(key)!.neighbors.length === 1);
  const result: string[] = [];
  for (const first of [...endpoints, ...graph.keys()]) {
    if (visited.has(first)) continue;
    const chain: Point[] = [];
    let current: number | undefined = first;
    while (current !== undefined && !visited.has(current)) {
      visited.add(current);
      const vertex: Vertex = graph.get(current)!;
      chain.push(vertex.point);
      current = vertex.neighbors.find(key => !visited.has(key));
    }
    if (chain.length < 2) continue;
    if (graph.get(first)!.neighbors.length === 2) chain.push(chain[0]);
    result.push('M' + chain[0].map(value => value.toFixed(1)).join(' '));
    for (let i = 1; i < chain.length - 1; i++) {
      const [x, y] = chain[i], [nx, ny] = chain[i + 1];
      result.push(`Q${x.toFixed(1)} ${y.toFixed(1)} ${((x+nx)/2).toFixed(1)} ${((y+ny)/2).toFixed(1)}`);
    }
    result.push('L' + chain[chain.length - 1].map(value => value.toFixed(1)).join(' '));
  }
  return result.join('');
}

/** Marching squares uses document-space samples and one global altitude interval across every seam. */
export function surveyContours(sheet: number): Contours {
  const existing = cache.get(sheet);
  if (existing) {
    cache.delete(sheet);
    cache.set(sheet, existing);
    return existing;
  }
  const stride = COLUMNS + 1;
  const grid = new Float64Array(stride * (ROWS + 1));
  for (let y = 0; y <= ROWS; y++) for (let x = 0; x <= COLUMNS; x++) {
    grid[y * stride + x] = elevation(x * STEP, sheet * SHEET_HEIGHT + y * STEP);
  }
  const levels = new Map<number, Map<number, Vertex>>();
  for (let y = 0; y < ROWS; y++) for (let x = 0; x < COLUMNS; x++) {
    const p = y * stride + x;
    const values = [grid[p], grid[p + 1], grid[p + stride + 1], grid[p + stride]];
    const lowest = Math.ceil(Math.min(...values) / INTERVAL);
    const highest = Math.floor(Math.max(...values) / INTERVAL);
    for (let level = lowest; level <= highest; level++) {
      const threshold = level * INTERVAL;
      let mask = 0;
      for (let i = 0; i < 4; i++) if (values[i] >= threshold) mask |= 1 << i;
      if (mask === 0 || mask === 15) continue;
      let edges = pairs[mask];
      if (!edges) {
        const centerHigh = (values[0] + values[1] + values[2] + values[3]) / 4 >= threshold;
        edges = (mask === 5) === centerHigh ? [0, 1, 2, 3] : [3, 0, 1, 2];
      }
      let graph = levels.get(level);
      if (!graph) levels.set(level, graph = new Map());
      const keys = [p * 2, (p + 1) * 2 + 1, (p + stride) * 2, p * 2 + 1];
      const connect = (edge: number, neighbor: number) => {
        const key = keys[edge];
        let vertex = graph!.get(key);
        if (!vertex) {
          const t = (threshold - values[edge]) / (values[(edge + 1) % 4] - values[edge]);
          const px = x + [t, 1, 1 - t, 0][edge];
          const py = y + [0, t, 1, 1 - t][edge];
          graph!.set(key, vertex = { point: [px * STEP, py * STEP], neighbors: [] });
        }
        vertex.neighbors.push(keys[neighbor]);
      };
      for (let i = 0; i < edges.length; i += 2) {
        connect(edges[i], edges[i + 1]); connect(edges[i + 1], edges[i]);
      }
    }
  }
  const result = { major: '', minor: '' };
  for (const [level, graph] of levels) result[level % 5 === 0 ? 'major' : 'minor'] += paths(graph);
  cache.set(sheet, result);
  if (cache.size > 14) cache.delete(cache.keys().next().value!);
  return result;
}
