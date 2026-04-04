import { useState, useEffect, useCallback, useRef } from "react";
import { fetchFeed, fetchEndorsedClaims, type EndorsedClaim } from "../services/api";
import { getAccessToken } from "../services/auth";
import { cacheGet, cacheSet } from "../services/cache";

const CACHE_KEY = "discover_feed";
const PAGE_SIZE = 50;

export function useDiscoverFeed() {
  const [claims, setClaims] = useState<EndorsedClaim[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const offset = useRef(0);
  const hasMore = useRef(true);

  const load = useCallback(async (reset = false) => {
    if (reset) {
      offset.current = 0;
      hasMore.current = true;
    }

    if (!hasMore.current && !reset) return;

    setLoading(true);
    setError(null);

    // Try cache on initial load
    if (reset) {
      const cached = await cacheGet<EndorsedClaim[]>(CACHE_KEY);
      if (cached) {
        setClaims(cached);
        setLoading(false);
      }
    }

    try {
      const token = await getAccessToken();
      let data: { claims: EndorsedClaim[] };

      if (token) {
        // Authenticated: personalized feed
        data = await fetchFeed(token, PAGE_SIZE, offset.current);
      } else {
        // Public: all endorsed claims
        data = await fetchEndorsedClaims({ limit: PAGE_SIZE, offset: offset.current });
      }

      if (reset) {
        setClaims(data.claims);
        await cacheSet(CACHE_KEY, data.claims);
      } else {
        setClaims((prev) => [...prev, ...data.claims]);
      }

      offset.current += data.claims.length;
      if (data.claims.length < PAGE_SIZE) {
        hasMore.current = false;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(true);
  }, [load]);

  const refresh = useCallback(() => load(true), [load]);
  const loadMore = useCallback(() => load(false), [load]);

  return { claims, loading, error, refresh, loadMore };
}
