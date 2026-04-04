import { useCallback } from "react";
import { cacheGet, cacheSet } from "../services/cache";

/**
 * Hook for network-first, cache-fallback pattern.
 * Wraps cacheGet/cacheSet with a typed key.
 */
export function useOfflineCache<T>(key: string) {
  const getCached = useCallback(() => cacheGet<T>(key), [key]);
  const setCached = useCallback((data: T) => cacheSet(key, data), [key]);

  return { getCached, setCached };
}
