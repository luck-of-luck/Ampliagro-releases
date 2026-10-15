import { describe, it, expect, vi } from 'vitest';
import { debounce, throttle } from '../../app/static/js/utils.js';

describe('utils', () => {
  it('debounce works correctly', async () => {
    vi.useFakeTimers();
    const mockFn = vi.fn();
    const debouncedFn = debounce(mockFn, 100);

    debouncedFn();
    debouncedFn();
    debouncedFn();

    expect(mockFn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(150);

    expect(mockFn).toHaveBeenCalledTimes(1);

    vi.useRealTimers();
  });

  it('throttle works correctly', () => {
    const mockFn = vi.fn();
    const throttledFn = throttle(mockFn, 100);

    throttledFn();
    throttledFn();
    throttledFn();

    expect(mockFn).toHaveBeenCalledTimes(1); // the first call goes through immediately
  });
});
