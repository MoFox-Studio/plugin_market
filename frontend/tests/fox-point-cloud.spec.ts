import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';

const rendering = vi.hoisted(() => ({ renderers: [] as any[] }));
vi.mock('three', async (importOriginal) => {
  const original = await importOriginal<typeof import('three')>();
  class WebGLRenderer {
    domElement = document.createElement('canvas');
    ratio = 1;
    setPixelRatio = vi.fn((ratio: number) => { this.ratio = ratio; });
    getPixelRatio = () => this.ratio;
    setClearColor = vi.fn();
    setSize = vi.fn();
    render = vi.fn();
    dispose = vi.fn();
    forceContextLoss = vi.fn();
    constructor() { rendering.renderers.push(this); }
  }
  return { ...original, WebGLRenderer };
});

let wrappers: VueWrapper[];
let frames: Map<number, FrameRequestCallback>;
let intersections: Array<IntersectionObserverCallback>;
let resizes: Array<ResizeObserverCallback>;
let hidden: boolean;
let reduced: boolean;
let width: number;
let height: number;
let samples: ReturnType<typeof vi.fn>;
let imageLoads: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.resetModules();
  rendering.renderers.length = 0;
  wrappers = [];
  frames = new Map();
  intersections = [];
  resizes = [];
  hidden = reduced = false;
  width = 400;
  height = 320;
  document.documentElement.removeAttribute('data-reduced-motion');
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden);
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => width);
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(() => height);
  vi.stubGlobal('innerWidth', 1440);
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    get matches() { return reduced; },
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
  let id = 0;
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
    frames.set(++id, callback);
    return id;
  }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn((key: number) => frames.delete(key)));
  vi.stubGlobal('IntersectionObserver', class {
    constructor(callback: IntersectionObserverCallback) { intersections.push(callback); }
    observe() {}
    disconnect() {}
  });
  vi.stubGlobal('ResizeObserver', class {
    constructor(callback: ResizeObserverCallback) { resizes.push(callback); }
    observe() {}
    disconnect() {}
  });
  imageLoads = vi.fn();
  vi.stubGlobal('Image', class {
    naturalWidth = 128;
    naturalHeight = 128;
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    set src(value: string) {
      imageLoads(value);
      queueMicrotask(() => this.onload?.());
    }
  });
  samples = vi.fn(function (this: HTMLCanvasElement) {
    return {
      drawImage: vi.fn(),
      getImageData: () => ({ data: new Uint8ClampedArray(this.width * this.height * 4).fill(255) }),
    };
  });
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(samples as any);
});

afterEach(() => {
  wrappers.forEach(wrapper => wrapper.unmount());
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

async function mountCloud() {
  await import('three');
  const { default: FoxPointCloud } = await import('@/components/FoxPointCloud.vue');
  const wrapper = mount(FoxPointCloud);
  wrappers.push(wrapper);
  intersections.at(-1)!([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
  await flushPromises();
  return wrapper;
}

function draw(time = 16) {
  const pending = [...frames.values()];
  frames.clear();
  pending.forEach(callback => callback(time));
}

describe('完整画质的标志动画', () => {
  test('保留原有桌面端粒子密度与着色器，同时每个动画帧仅绘制一次', async () => {
    const wrapper = await mountCloud();
    const renderer = rendering.renderers[0];
    expect(wrapper.find('.logo-scan').exists()).toBe(true);
    expect(wrapper.find('.mofox-original-logo').attributes('width')).toBe('320');
    expect(renderer.render).not.toHaveBeenCalled();
    expect(frames.size).toBe(1);
    draw();
    expect(renderer.render).toHaveBeenCalledOnce();
    const [scene] = renderer.render.mock.lastCall;
    const cloud = scene.children[0];
    expect(cloud.geometry.attributes.position.count).toBe(128 * 128);
    expect(cloud.geometry.attributes.sourceAlpha.count).toBe(128 * 128);
    expect(cloud.material.vertexShader).toContain('sin(position.y * 2.4 - time * .75)');
    expect(cloud.material.uniforms.time.value).toBe(0.016);
    draw(32);
    expect(renderer.render).toHaveBeenCalledTimes(2);
    expect(frames.size).toBe(1);
  });

  test('保持原有移动端采样密度', async () => {
    vi.stubGlobal('innerWidth', 600);
    await mountCloud();
    draw();
    const [scene] = rendering.renderers[0].render.mock.lastCall;
    expect(scene.children[0].geometry.attributes.position.count).toBe(88 * 88);
  });

  test('返回路由时复用不可变像素数据，并释放每个 WebGL 场景', async () => {
    const first = await mountCloud();
    draw();
    const firstRenderer = rendering.renderers[0];
    const firstPositions = firstRenderer.render.mock.lastCall[0].children[0].geometry.attributes.position.array;
    first.unmount();
    wrappers.splice(wrappers.indexOf(first), 1);
    expect(firstRenderer.dispose).toHaveBeenCalledOnce();
    expect(firstRenderer.forceContextLoss).toHaveBeenCalledOnce();
    expect(frames.size).toBe(0);

    await mountCloud();
    draw();
    const secondPositions = rendering.renderers[1].render.mock.lastCall[0].children[0].geometry.attributes.position.array;
    expect(imageLoads).toHaveBeenCalledOnce();
    expect(samples).toHaveBeenCalledOnce();
    expect(secondPositions).toBe(firstPositions);
  });

  test('合并连续尺寸变化，不重复分配画布或额外绘制', async () => {
    await mountCloud();
    draw();
    const renderer = rendering.renderers[0];
    expect(renderer.setSize).toHaveBeenCalledOnce();
    for (let i = 0; i < 10; i++) resizes[0]([], {} as ResizeObserver);
    expect(renderer.render).toHaveBeenCalledOnce();
    draw();
    expect(renderer.setSize).toHaveBeenCalledOnce();
    expect(renderer.render).toHaveBeenCalledTimes(2);
    width = 500;
    for (let i = 0; i < 10; i++) resizes[0]([], {} as ResizeObserver);
    draw();
    expect(renderer.setSize).toHaveBeenCalledTimes(2);
    expect(renderer.setSize).toHaveBeenLastCalledWith(500, 320);
    expect(renderer.render).toHaveBeenCalledTimes(3);
  });

  test('离开视口或文档隐藏时暂停，之后以正常帧率恢复', async () => {
    await mountCloud();
    draw();
    const renderer = rendering.renderers[0];
    intersections[0]([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver);
    expect(frames.size).toBe(0);
    hidden = true;
    intersections[0]([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    expect(frames.size).toBe(0);
    hidden = false;
    document.dispatchEvent(new Event('visibilitychange'));
    expect(frames.size).toBe(1);
    draw();
    expect(renderer.render).toHaveBeenCalledTimes(2);
    expect(frames.size).toBe(1);
  });

  test('减少动态效果偏好保留原有标志，且不启动 WebGL', async () => {
    reduced = true;
    const wrapper = await mountCloud();
    expect(wrapper.find('.mofox-original-logo').exists()).toBe(true);
    expect(rendering.renderers).toHaveLength(0);
    expect(frames.size).toBe(0);
    expect(imageLoads).not.toHaveBeenCalled();
  });
});
