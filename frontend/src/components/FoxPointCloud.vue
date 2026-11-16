<script lang="ts">
type ThreeModule = typeof import('three');
interface LogoPoints {
  positions: Float32Array;
  colors: Float32Array;
  alphas: Float32Array;
}

// 源像素及其线性颜色不可变。跨路由访问复用原有的两种采样密度，
// 避免为每个 WebGL 场景重复解码和采样同一标志。
let logoImage: Promise<HTMLImageElement> | null = null;
const pointCache = new Map<number, LogoPoints>();
function loadLogo(): Promise<HTMLImageElement> {
  if (!logoImage) {
    logoImage = new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        image.onload = image.onerror = null;
        resolve(image);
      };
      image.onerror = () => {
        image.onload = image.onerror = null;
        reject(new Error('标志图像不可用'));
      };
      image.src = '/logo.png';
    }).catch((error) => {
      logoImage = null;
      throw error;
    });
  }
  return logoImage;
}
function logoPoints(image: HTMLImageElement, width: number, T: ThreeModule): LogoPoints {
  const cached = pointCache.get(width);
  if (cached) return cached;
  const sample = document.createElement('canvas');
  sample.width = width;
  sample.height = Math.round((width * image.naturalHeight) / image.naturalWidth);
  const context = sample.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('标志图像采样不可用');
  context.drawImage(image, 0, 0, sample.width, sample.height);
  const pixels = context.getImageData(0, 0, sample.width, sample.height).data;
  const positions: number[] = [], colors: number[] = [], alphas: number[] = [];
  const color = new T.Color();
  for (let y = 0; y < sample.height; y++) {
    for (let x = 0; x < sample.width; x++) {
      const i = (y * sample.width + x) * 4;
      const alpha = pixels[i + 3] / 255;
      if (alpha < 0.05) continue;
      const r = pixels[i] / 255, g = pixels[i + 1] / 255, b = pixels[i + 2] / 255;
      const luminance = r * 0.2126 + g * 0.7152 + b * 0.0722;
      positions.push(
        (x / (sample.width - 1) - 0.5) * 4.2,
        ((0.5 - y / (sample.height - 1)) * 4.2 * sample.height) / sample.width,
        (0.5 - luminance) * 0.08,
      );
      color.setRGB(r, g, b, T.SRGBColorSpace);
      colors.push(color.r, color.g, color.b);
      alphas.push(alpha);
    }
  }
  sample.width = sample.height = 0;
  const points = {
    positions: new Float32Array(positions),
    colors: new Float32Array(colors),
    alphas: new Float32Array(alphas),
  };
  pointCache.set(width, points);
  return points;
}
</script>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';
import FoxMark from './FoxMark.vue';

const host = ref<HTMLElement | null>(null);
const ready = ref(false);
const reduced = ref(false);
const playing = ref(false);
let cleanup = () => {};
let disposed = false;

onMounted(() => {
  if (!host.value) return;
  const root: HTMLElement = host.value;
  const media = window.matchMedia('(prefers-reduced-motion: reduce)');
  let visible = false;
  let initializing = false;
  let failed = false;
  let frame = 0;
  let render: ((time: number) => void) | null = null;
  let releaseScene = () => {};

  function stop() {
    cancelAnimationFrame(frame);
    frame = 0;
    playing.value = false;
  }
  function canAnimate() {
    return !disposed && visible && !document.hidden && !reduced.value;
  }
  function tick(time: number) {
    frame = 0;
    if (!canAnimate() || !render) {
      stop();
      return;
    }
    render(time);
    frame = requestAnimationFrame(tick);
  }
  function resume() {
    if (!canAnimate() || !render) return;
    playing.value = true;
    if (!frame) frame = requestAnimationFrame(tick);
  }
  async function initialize() {
    if (initializing || render || failed || !canAnimate()) return;
    initializing = true;
    try {
      // 两个网络请求互不依赖，应并发启动而非串行执行。
      const [image, T] = await Promise.all([loadLogo(), import('three')]);
      if (!canAnimate()) return;

      // 每个粒子都来自原始 PNG 像素的透明度和 RGB 颜色。
      // 不使用手绘轮廓、替代调色板或生成的狐狸几何模型。
      const width = window.innerWidth < 760 ? 88 : 128;
      const { positions, colors, alphas } = logoPoints(image, width, T);
      if (!positions.length) return;

      const renderer = new T.WebGLRenderer({
        alpha: true,
        antialias: false,
        powerPreference: 'low-power',
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
      renderer.setClearColor(0, 0);
      const scene = new T.Scene();
      const camera = new T.OrthographicCamera(-3, 3, 3, -3, 0.1, 10);
      camera.position.z = 4;
      const geometry = new T.BufferGeometry();
      const material = new T.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        uniforms: {
          time: { value: 0 },
          ratio: { value: renderer.getPixelRatio() },
        },
        vertexShader: `
          uniform float time;
          uniform float ratio;
          attribute vec3 color;
          attribute float sourceAlpha;
          varying vec3 pixelColor;
          varying float pointAlpha;
          void main() {
            float scan = .5 + .5 * sin(position.y * 2.4 - time * .75);
            pixelColor = color;
            pointAlpha = sourceAlpha * (.12 + scan * .36);
            gl_PointSize = (1.2 + scan * .8) * ratio;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: `
          varying vec3 pixelColor;
          varying float pointAlpha;
          void main() {
            float radius = length(gl_PointCoord - .5);
            if (radius > .5) discard;
            gl_FragColor = vec4(pixelColor, pointAlpha * (1.0 - smoothstep(.2, .5, radius)));
            #include <colorspace_fragment>
          }
        `,
      });
      let resizeObserver: ResizeObserver | null = null;
      let released = false;
      const lost = (event: Event) => {
        event.preventDefault();
        failed = true;
        stop();
        releaseScene();
      };
      releaseScene = () => {
        if (released) return;
        released = true;
        ready.value = false;
        render = null;
        resizeObserver?.disconnect();
        window.removeEventListener('resize', resize);
        renderer.domElement.removeEventListener('webglcontextlost', lost);
        geometry.dispose();
        material.dispose();
        renderer.dispose();
        renderer.forceContextLoss();
        renderer.domElement.remove();
      };
      geometry.setAttribute(
        'position',
        new T.BufferAttribute(positions, 3),
      );
      geometry.setAttribute('color', new T.BufferAttribute(colors, 3));
      geometry.setAttribute(
        'sourceAlpha',
        new T.BufferAttribute(alphas, 1),
      );
      scene.add(new T.Points(geometry, material));
      root.appendChild(renderer.domElement);
      renderer.domElement.addEventListener('webglcontextlost', lost);
      let resizePending = true;
      let renderedWidth = 0, renderedHeight = 0;
      function resize() {
        // 内容尺寸相同时，ResizeObserver 也可能重复触发。
        // 下一次常规动画帧只调整一次尺寸并绘制一次。
        resizePending = true;
      }
      function applyResize() {
        if (!resizePending) return;
        resizePending = false;
        if (disposed || released) return;
        const w = Math.max(1, root.clientWidth),
          h = Math.max(1, root.clientHeight);
        if (w === renderedWidth && h === renderedHeight) return;
        renderedWidth = w;
        renderedHeight = h;
        const scale = (Math.min(w, h) * 0.82) / 4.2;
        renderer.setSize(w, h);
        camera.left = -w / (2 * scale);
        camera.right = w / (2 * scale);
        camera.top = h / (2 * scale);
        camera.bottom = -h / (2 * scale);
        camera.updateProjectionMatrix();
      }
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(resize);
        resizeObserver.observe(root);
      } else window.addEventListener('resize', resize);
      render = (time) => {
        applyResize();
        material.uniforms.time.value = time * 0.001;
        renderer.render(scene, camera);
      };
      ready.value = true;
      resume();
    } catch {
      failed = true;
      stop();
      releaseScene();
    } finally {
      initializing = false;
    }
  }
  function syncMotion() {
    reduced.value =
      media.matches ||
      document.documentElement.dataset.reducedMotion === 'reduce';
    if (reduced.value) stop();
    else {
      void initialize();
      resume();
    }
  }
  function visibility() {
    if (document.hidden) stop();
    else {
      void initialize();
      resume();
    }
  }
  const motionObserver = new MutationObserver(syncMotion);
  motionObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-reduced-motion'],
  });
  let intersection: IntersectionObserver | null = null;
  if (typeof IntersectionObserver !== 'undefined') {
    intersection = new IntersectionObserver(
      (entries) => {
        visible = entries[0]?.isIntersecting ?? false;
        if (visible) {
          void initialize();
          resume();
        } else stop();
      },
      { rootMargin: '0px' },
    );
    intersection.observe(root);
  } else visible = true;
  media.addEventListener('change', syncMotion);
  document.addEventListener('visibilitychange', visibility);
  syncMotion();
  cleanup = () => {
    stop();
    releaseScene();
    intersection?.disconnect();
    motionObserver.disconnect();
    media.removeEventListener('change', syncMotion);
    document.removeEventListener('visibilitychange', visibility);
  };
});
onBeforeUnmount(() => {
  disposed = true;
  cleanup();
});
</script>
<template>
  <div class="fox-cloud" :class="{ 'is-playing': playing }">
    <div
      ref="host"
      class="logo-pixel-cloud"
      :class="{ 'is-ready': ready && !reduced }"
      aria-hidden="true"
    />
    <div class="original-logo-frame">
      <span class="logo-register logo-register--top" aria-hidden="true" />
      <span class="logo-register logo-register--bottom" aria-hidden="true" />
      <FoxMark :size="320" alt="MoFox 原始品牌图标" />
      <span class="logo-scan" aria-hidden="true" />
    </div>
  </div>
</template>
<style scoped>
.fox-cloud {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
}
.logo-pixel-cloud {
  position: absolute;
  inset: 0;
  opacity: 0;
  pointer-events: none;
}
.logo-pixel-cloud.is-ready {
  opacity: 1;
}
.original-logo-frame {
  position: relative;
  z-index: 1;
  width: min(320px, 72%);
  padding: 20px;
}
.original-logo-frame :deep(.mofox-original-logo) {
  width: 100%;
  height: auto;
}
.logo-register {
  position: absolute;
  width: 28px;
  height: 28px;
  border-color: var(--blue-300);
  border-style: solid;
}
.logo-register--top {
  top: 0;
  left: 0;
  border-width: 1px 0 0 1px;
}
.logo-register--bottom {
  bottom: 0;
  right: 0;
  border-width: 0 1px 1px 0;
}
.logo-scan {
  position: absolute;
  top: 8%;
  bottom: 8%;
  left: -10px;
  width: 2px;
  overflow: hidden;
  background: var(--line);
}
.logo-scan::after {
  content: '';
  display: block;
  width: 100%;
  height: 24%;
  background: var(--blue-500);
  animation: logo-scan 4s ease-in-out infinite alternate;
  animation-play-state: paused;
}
.is-playing .logo-scan::after {
  animation-play-state: running;
}
@keyframes logo-scan {
  to {
    transform: translateY(320%);
  }
}
@media (prefers-reduced-motion: reduce) {
  .logo-scan::after {
    animation: none;
  }
}
:global(:root[data-reduced-motion='reduce'] .logo-scan::after) {
  animation: none;
}
</style>
