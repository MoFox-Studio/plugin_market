import type { Contours } from './surveyContours';

export interface SurveyGeometryRequest { id: number; sheet: number }
export interface SurveyGeometryResult extends SurveyGeometryRequest { geometry: Contours }
export interface SurveyGeometryWorker {
  onmessage: ((event: MessageEvent<SurveyGeometryResult>) => void) | null;
  onerror: ((event: ErrorEvent) => void) | null;
  onmessageerror: ((event: MessageEvent) => void) | null;
  postMessage(message: SurveyGeometryRequest): void;
  terminate(): void;
}
interface GeometryOptions {
  workerFactory?: () => SurveyGeometryWorker;
  generate?: (sheet: number) => Contours | Promise<Contours>;
  cacheLimit?: number;
}
interface Observer { sheets: number[]; update(): void }

/** 一次只处理一个图幅，共享计算结果，并依据当前视口生成队列。 */
export class SurveyGeometryScheduler {
  private readonly cache = new Map<number, Contours>();
  private readonly observers = new Set<Observer>();
  private readonly workerFactory: () => SurveyGeometryWorker;
  private readonly generate: (sheet: number) => Contours | Promise<Contours>;
  private readonly cacheLimit: number;
  private worker: SurveyGeometryWorker | null = null;
  private workerUnavailable = false;
  private active: SurveyGeometryRequest | null = null;
  private sequence = 0;
  private fallbackTimer: ReturnType<typeof setTimeout> | undefined;

  constructor(options: GeometryOptions = {}) {
    this.workerFactory = options.workerFactory || (() =>
      new Worker(new URL('./surveyContours.worker.ts', import.meta.url), { type: 'module' }));
    this.generate = options.generate || (async (sheet) =>
      (await import('./surveyContours')).surveyContours(sheet));
    this.cacheLimit = Math.max(1, options.cacheLimit ?? 14);
  }

  get(sheet: number): Contours | undefined {
    const geometry = this.cache.get(sheet);
    if (geometry) {
      this.cache.delete(sheet);
      this.cache.set(sheet, geometry);
    }
    return geometry;
  }

  subscribe(update: () => void) {
    const observer: Observer = { sheets: [], update };
    this.observers.add(observer);
    return {
      setSheets: (sheets: readonly number[]) => {
        if (!this.observers.has(observer)) return;
        observer.sheets = [...new Set(sheets.filter(sheet => Number.isSafeInteger(sheet) && sheet >= 0))];
        // 优先处理最近更新的视口，不派发队列中已过时的图幅。
        this.observers.delete(observer);
        this.observers.add(observer);
        this.trimCache();
        observer.update();
        this.pump();
      },
      dispose: () => {
        this.observers.delete(observer);
        if (!this.observers.size) this.stop();
        this.trimCache();
      },
    };
  }

  private requestedSheets() {
    return [...new Set([...this.observers].reverse().flatMap(observer => observer.sheets))];
  }

  private trimCache() {
    const visible = new Set(this.requestedSheets());
    for (const sheet of this.cache.keys()) {
      if (this.cache.size <= this.cacheLimit) break;
      // 即使视口异常高，也保留当前显示的图幅。
      if (!visible.has(sheet)) this.cache.delete(sheet);
    }
  }

  private pump() {
    if (this.active) return;
    const sheet = this.requestedSheets().find(index => !this.cache.has(index));
    if (sheet === undefined) return;
    const request = this.active = { id: ++this.sequence, sheet };
    if (!this.workerUnavailable) {
      try {
        if (!this.worker) {
          this.worker = this.workerFactory();
          this.worker.onmessage = event => this.complete(event.data);
          this.worker.onerror = event => {
            event.preventDefault();
            this.failWorker();
          };
          this.worker.onmessageerror = () => this.failWorker();
        }
        this.worker.postMessage(request);
        return;
      } catch {
        this.failWorker();
        return;
      }
    }
    // Worker 不受支持或被阻止时，仍使用完全相同的几何算法。先让出执行权，
    // 避免路由渲染与待处理输入等待回退计算。
    this.fallbackTimer = setTimeout(async () => {
      this.fallbackTimer = undefined;
      if (this.active?.id !== request.id) return;
      if (!this.requestedSheets().includes(sheet)) {
        this.active = null;
        this.pump();
        return;
      }
      const geometry = await this.generate(sheet);
      this.complete({ ...request, geometry });
    }, 0);
  }

  private complete(result: SurveyGeometryResult) {
    if (result.id !== this.active?.id || result.sheet !== this.active.sheet) return;
    if (typeof result.geometry?.minor !== 'string' || typeof result.geometry?.major !== 'string') {
      this.failWorker();
      return;
    }
    this.active = null;
    this.cache.set(result.sheet, result.geometry);
    this.trimCache();
    for (const observer of this.observers) {
      if (observer.sheets.includes(result.sheet)) observer.update();
    }
    this.pump();
  }

  private failWorker() {
    this.workerUnavailable = true;
    this.stop();
    this.pump();
  }

  private stop() {
    if (this.fallbackTimer !== undefined) clearTimeout(this.fallbackTimer);
    this.fallbackTimer = undefined;
    if (this.worker) {
      this.worker.onmessage = this.worker.onerror = this.worker.onmessageerror = null;
      this.worker.terminate();
      this.worker = null;
    }
    this.active = null;
  }
}

export const surveyGeometry = new SurveyGeometryScheduler();
