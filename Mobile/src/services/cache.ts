import AsyncStorage from "@react-native-async-storage/async-storage";

const CACHE_PREFIX = "ss_cache:";
const TTL_MS = 60 * 60 * 1000; // 1 hour
const MAX_ENTRIES = 100;

interface CacheEntry<T> {
  data: T;
  ts: number;
}

/** Read from cache. Returns null if expired or missing. */
export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return null;
    const entry: CacheEntry<T> = JSON.parse(raw);
    if (Date.now() - entry.ts > TTL_MS) {
      await AsyncStorage.removeItem(CACHE_PREFIX + key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

/** Write to cache with TTL. Evicts oldest entries if over MAX_ENTRIES. */
export async function cacheSet<T>(key: string, data: T): Promise<void> {
  try {
    const entry: CacheEntry<T> = { data, ts: Date.now() };
    await AsyncStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
    await evictIfNeeded();
  } catch {
    // Cache write failure is non-fatal
  }
}

/** Remove a specific cache entry. */
export async function cacheRemove(key: string): Promise<void> {
  await AsyncStorage.removeItem(CACHE_PREFIX + key).catch(() => {});
}

/** Evict oldest entries to stay within MAX_ENTRIES. */
async function evictIfNeeded(): Promise<void> {
  const allKeys = await AsyncStorage.getAllKeys();
  const cacheKeys = allKeys.filter((k) => k.startsWith(CACHE_PREFIX));

  if (cacheKeys.length <= MAX_ENTRIES) return;

  // Read timestamps and sort by oldest first
  const entries: { key: string; ts: number }[] = [];
  for (const key of cacheKeys) {
    try {
      const raw = await AsyncStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw) as CacheEntry<unknown>;
        entries.push({ key, ts: parsed.ts });
      }
    } catch {
      entries.push({ key, ts: 0 });
    }
  }

  entries.sort((a, b) => a.ts - b.ts);
  const toRemove = entries.slice(0, entries.length - MAX_ENTRIES);
  await AsyncStorage.multiRemove(toRemove.map((e) => e.key));
}

/** Clear all cached data. */
export async function cacheClearAll(): Promise<void> {
  const allKeys = await AsyncStorage.getAllKeys();
  const cacheKeys = allKeys.filter((k) => k.startsWith(CACHE_PREFIX));
  if (cacheKeys.length > 0) {
    await AsyncStorage.multiRemove(cacheKeys);
  }
}
