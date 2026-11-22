import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue';

export const WORLD_WIDTH = 1600;
export const SHEET_HEIGHT = 640;

function projection(width: number, height: number, scroll: number) {
  const scale = Math.max(0.74, width / WORLD_WIDTH);
  const first = Math.max(0, Math.floor(scroll / (SHEET_HEIGHT * scale)) - 1);
  const count = Math.ceil(height / (SHEET_HEIGHT * scale)) + 3;
  return { scale, first, count, width, height };
}

const camera = shallowRef(projection(1440, 900, 0));
let consumers = 0;
function positionCamera() {
  const scroll = Math.max(0, window.scrollY);
  const next = projection(window.innerWidth, window.innerHeight, scroll);
  const old = camera.value;
  if (next.first !== old.first || next.width !== old.width || next.height !== old.height) {
    camera.value = next;
  }
  // The foreground register and background contour sheet share one map origin.
  const x = (next.width - WORLD_WIDTH * next.scale) * 0.74;
  const y = next.first * SHEET_HEIGHT * next.scale - scroll;
  document.documentElement.style.setProperty('--survey-sheet-x', x + 'px');
  document.documentElement.style.setProperty('--survey-sheet-y', y + 'px');
}

export function useSurveyWorld() {
  onMounted(() => {
    if (++consumers > 1) return;
    positionCamera();
    window.addEventListener('scroll', positionCamera, { passive: true });
    window.addEventListener('resize', positionCamera, { passive: true });
    window.addEventListener('pageshow', positionCamera);
  });
  onBeforeUnmount(() => {
    if (--consumers > 0) return;
    window.removeEventListener('scroll', positionCamera);
    window.removeEventListener('resize', positionCamera);
    window.removeEventListener('pageshow', positionCamera);
    document.documentElement.style.removeProperty('--survey-sheet-x');
    document.documentElement.style.removeProperty('--survey-sheet-y');
  });
  const sheets = computed(() => Array.from({ length: camera.value.count }, (_, i) => camera.value.first + i));
  const viewBox = computed(() => `0 0 ${WORLD_WIDTH} ${SHEET_HEIGHT * camera.value.count}`);
  const dimensions = computed(() => ({
    width: WORLD_WIDTH * camera.value.scale + 'px',
    height: SHEET_HEIGHT * camera.value.count * camera.value.scale + 'px',
  }));
  return { camera, sheets, viewBox, dimensions };
}
