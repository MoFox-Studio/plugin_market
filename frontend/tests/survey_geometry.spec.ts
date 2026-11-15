import { afterEach, describe, expect, test, vi } from 'vitest';
import { SurveyGeometryScheduler } from '@/composables/surveyGeometry';
import type { SurveyGeometryRequest, SurveyGeometryResult, SurveyGeometryWorker } from '@/composables/surveyGeometry';
import { surveyContours } from '@/composables/surveyContours';

class GeometryWorker implements SurveyGeometryWorker {
  onmessage: SurveyGeometryWorker['onmessage'] = null;
  onerror: SurveyGeometryWorker['onerror'] = null;
  onmessageerror: SurveyGeometryWorker['onmessageerror'] = null;
  requests: SurveyGeometryRequest[] = [];
  terminate = vi.fn();
  postMessage(request: SurveyGeometryRequest) { this.requests.push(request); }
  finish(request = this.requests[this.requests.length - 1]) {
    this.onmessage?.({ data: { ...request, geometry: { major: `major-${request.sheet}`, minor: `minor-${request.sheet}` } } } as MessageEvent<SurveyGeometryResult>);
  }
}

afterEach(() => vi.useRealTimers());

describe('survey geometry scheduling', () => {
  test('deduplicates shared sheets and skips obsolete queued work after a fast scroll', () => {
    const worker = new GeometryWorker();
    const scheduler = new SurveyGeometryScheduler({ workerFactory: () => worker });
    const first = scheduler.subscribe(vi.fn());
    const second = scheduler.subscribe(vi.fn());
    first.setSheets([0, 1, 2, 2]);
    second.setSheets([0, 1]);
    expect(worker.requests.map(request => request.sheet)).toEqual([0]);

    first.setSheets([8, 9]);
    second.setSheets([8, 9]);
    worker.finish();
    expect(worker.requests.map(request => request.sheet)).toEqual([0, 8]);
    worker.finish();
    first.setSheets([8, 9]);
    expect(worker.requests.map(request => request.sheet)).toEqual([0, 8, 9]);
    worker.finish();
    second.setSheets([9, 8]);
    expect(worker.requests).toHaveLength(3);
    expect(scheduler.get(9)).toEqual({ major: 'major-9', minor: 'minor-9' });
    first.dispose();
    expect(worker.terminate).not.toHaveBeenCalled();
    second.dispose();
    expect(worker.terminate).toHaveBeenCalledOnce();
  });

  test('retains cached results across consumers, evicts old sheets, and ignores disposed results', () => {
    const workers: GeometryWorker[] = [];
    const scheduler = new SurveyGeometryScheduler({
      cacheLimit: 2,
      workerFactory: () => { const worker = new GeometryWorker(); workers.push(worker); return worker; },
    });
    const observer = scheduler.subscribe(vi.fn());
    observer.setSheets([0]);
    workers[0].finish();
    observer.setSheets([1]);
    workers[0].finish();
    observer.setSheets([2]);
    workers[0].finish();
    expect(scheduler.get(0)).toBeUndefined();
    observer.dispose();

    const update = vi.fn();
    const remounted = scheduler.subscribe(update);
    remounted.setSheets([1]);
    expect(workers).toHaveLength(1);
    expect(scheduler.get(1)?.major).toBe('major-1');
    remounted.setSheets([0]);
    expect(workers[1].requests[0].sheet).toBe(0);
    const staleListener = workers[1].onmessage!;
    const request = workers[1].requests[0];
    remounted.dispose();
    update.mockClear();
    staleListener({ data: { ...request, geometry: { major: 'stale', minor: 'stale' } } } as MessageEvent<SurveyGeometryResult>);
    expect(update).not.toHaveBeenCalled();
    expect(scheduler.get(0)).toBeUndefined();
  });

  test('keeps every requested sheet even when the viewport exceeds the normal cache limit', () => {
    const worker = new GeometryWorker();
    const scheduler = new SurveyGeometryScheduler({ cacheLimit: 1, workerFactory: () => worker });
    const observer = scheduler.subscribe(vi.fn());
    observer.setSheets([0, 1, 2]);
    worker.finish();
    worker.finish();
    worker.finish();
    expect(worker.requests).toHaveLength(3);
    expect([0, 1, 2].every(sheet => scheduler.get(sheet))).toBe(true);
    observer.dispose();
  });

  test('falls back to the complete original algorithm when workers cannot start', async () => {
    vi.useFakeTimers();
    const scheduler = new SurveyGeometryScheduler({ workerFactory: () => { throw new Error('Worker blocked'); } });
    const observer = scheduler.subscribe(vi.fn());
    observer.setSheets([0]);
    expect(scheduler.get(0)).toBeUndefined();
    await vi.runAllTimersAsync();
    const geometry = scheduler.get(0);
    expect(geometry).toEqual(surveyContours(0));
    expect(geometry!.minor.length).toBeGreaterThan(10000);
    expect(geometry!.major.length).toBeGreaterThan(1000);
    observer.dispose();
  });

  test('retries only the current viewport through the fallback after a worker failure', async () => {
    vi.useFakeTimers();
    const worker = new GeometryWorker();
    const generate = vi.fn((sheet: number) => ({ major: `major-${sheet}`, minor: `minor-${sheet}` }));
    const scheduler = new SurveyGeometryScheduler({ workerFactory: () => worker, generate });
    const observer = scheduler.subscribe(vi.fn());
    observer.setSheets([1, 2]);
    observer.setSheets([20]);
    worker.onerror!({ preventDefault: vi.fn() } as unknown as ErrorEvent);
    await vi.runAllTimersAsync();
    expect(generate.mock.calls).toEqual([[20]]);
    expect(scheduler.get(20)?.major).toBe('major-20');
    expect(worker.terminate).toHaveBeenCalledOnce();
    observer.dispose();
  });
});
