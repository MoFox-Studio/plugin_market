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

/** One in-flight sheet, shared results, and a queue derived from current viewports. */
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
        // Most recent viewport goes first; obsolete queued sheets are never dispatched.
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
      // Keep currently displayed sheets even in unusually tall viewports.
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
    // Unsupported/blocked workers retain the exact geometry algorithm. Yield first,
    // so route rendering and pending input do not wait for the fallback computation.
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
