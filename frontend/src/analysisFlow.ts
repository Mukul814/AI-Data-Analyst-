export async function runAnalysisRequest<T>(
  request: () => Promise<T>,
  setBusy: (busy: boolean) => void,
  clearPrevious: () => void,
  setResult: (result: T) => void,
): Promise<T> {
  clearPrevious();
  setBusy(true);
  try {
    const result = await request();
    setResult(result);
    return result;
  } finally {
    setBusy(false);
  }
}
