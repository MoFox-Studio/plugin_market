import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue';
import { SHEET_HEIGHT, WORLD_WIDTH } from './surveyCoordinates';
export { SHEET_HEIGHT, WORLD_WIDTH } from './surveyCoordinates';

export interface SurveyPosition { x: number; y: number }
type PositionListener = (position: Readonly<SurveyPosition>) => void;
function projection(width: number, height: number, scroll: number) {
  const scale = Math.max(0.74, width / WORLD_WIDTH);
  const first = Math.max(0, Math.floor(scroll / (SHEET_HEIGHT * scale)) - 1);
  const count = Math.ceil(height / (SHEET_HEIGHT * scale)) + 3;
  return { scale, first, count, width, height };
}
const camera = shallowRef(projection(1440, 900, 0));
const listeners = new Set<PositionListener>();
let consumers = 0;
let frame = 0;
let position: SurveyPosition = { x: 0, y: 0 };
function positionCamera() {
  frame = 0;
  const scroll = Math.max(0, window.scrollY);
  const next = projection(window.innerWidth, window.innerHeight, scroll);
  const old = camera.value;
  if (next.first !== old.first || next.width !== old.width || next.height !== old.height) camera.value = next;
  // Only the two map SVGs move. Do not invalidate inherited styles on the page.
  const x = (next.width - WORLD_WIDTH * next.scale) * 0.74;
  const y = next.first * SHEET_HEIGHT * next.scale - scroll;
  if (x !== position.x || y !== position.y) {
    position = { x, y };
    for (const listener of listeners) listener(position);
  }
}
function schedulePosition() {
  if (!frame) frame = requestAnimationFrame(positionCamera);
}

export function useSurveyWorld(onPosition?: PositionListener) {
  onMounted(() => {
    if (++consumers === 1) {
      positionCamera();
      window.addEventListener('scroll', schedulePosition, { passive: true });
      window.addEventListener('resize', schedulePosition, { passive: true });
      window.addEventListener('pageshow', schedulePosition);
    }
    if (onPosition) listeners.add(onPosition);
    onPosition?.(position);
  });
  onBeforeUnmount(() => {
    if (onPosition) listeners.delete(onPosition);
    if (--consumers > 0) return;
    window.removeEventListener('scroll', schedulePosition);
    window.removeEventListener('resize', schedulePosition);
    window.removeEventListener('pageshow', schedulePosition);
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
  });
  const sheets = computed(() => Array.from({ length: camera.value.count }, (_, i) => camera.value.first + i));
  const viewBox = computed(() => `0 0 ${WORLD_WIDTH} ${SHEET_HEIGHT * camera.value.count}`);
  const dimensions = computed(() => ({
    width: WORLD_WIDTH * camera.value.scale + 'px',
    height: SHEET_HEIGHT * camera.value.count * camera.value.scale + 'px',
  }));
  return { camera, sheets, viewBox, dimensions };
}
