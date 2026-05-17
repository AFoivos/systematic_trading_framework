import { useEffect, useState, type DependencyList } from "react";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

export function useAsyncResource<T>(
  loader: () => Promise<T>,
  deps: DependencyList,
  enabled = true
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, error: null, loading: false });

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let cancelled = false;
    setState((current) => ({ ...current, loading: true, error: null }));
    loader()
      .then((data) => {
        if (!cancelled) {
          setState({ data, error: null, loading: false });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ data: null, error: error instanceof Error ? error.message : String(error), loading: false });
        }
      });
    return () => {
      cancelled = true;
    };
  }, deps);

  return state;
}
