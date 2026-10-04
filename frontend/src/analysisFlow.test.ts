import { describe, expect, it, vi } from 'vitest';
import { runAnalysisRequest } from './analysisFlow';

describe('analysis request state', () => {
  it('clears the old result before a failed request and exits loading state', async () => {
    let result: string | null = 'previous answer';
    let busy = false;
    const clear = vi.fn(() => { result = null; });
    const setBusy = vi.fn((value: boolean) => { busy = value; });
    const setResult = vi.fn((value: string) => { result = value; });

    await expect(runAnalysisRequest(
      () => Promise.reject(new Error('offline')),
      setBusy,
      clear,
      setResult,
    )).rejects.toThrow('offline');

    expect(clear).toHaveBeenCalledOnce();
    expect(result).toBeNull();
    expect(setResult).not.toHaveBeenCalled();
    expect(busy).toBe(false);
    expect(setBusy).toHaveBeenNthCalledWith(1, true);
    expect(setBusy).toHaveBeenNthCalledWith(2, false);
  });

  it('replaces the previous result after a successful request', async () => {
    let result: string | null = 'previous answer';
    const next = await runAnalysisRequest(
      async () => 'new answer',
      () => undefined,
      () => { result = null; },
      value => { result = value; },
    );
    expect(next).toBe('new answer');
    expect(result).toBe('new answer');
  });
});
