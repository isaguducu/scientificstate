import { useState, useEffect } from "react";
import {
  fetchClaimDetail,
  fetchCitations,
  fetchImpact,
  type EndorsedClaim,
  type CitationChain,
  type ImpactScore,
} from "../services/api";
import { cacheGet, cacheSet } from "../services/cache";

export function useClaimDetail(claimId: string) {
  const [claim, setClaim] = useState<EndorsedClaim | null>(null);
  const [citations, setCitations] = useState<CitationChain | null>(null);
  const [impact, setImpact] = useState<ImpactScore | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);

      // Try cache
      const cachedClaim = await cacheGet<EndorsedClaim>(`claim:${claimId}`);
      if (cachedClaim && !cancelled) setClaim(cachedClaim);

      try {
        // Fetch all three in parallel
        const [claimRes, citRes, impactRes] = await Promise.allSettled([
          fetchClaimDetail(claimId),
          fetchCitations(claimId),
          fetchImpact(claimId),
        ]);

        if (cancelled) return;

        if (claimRes.status === "fulfilled") {
          setClaim(claimRes.value.claim);
          await cacheSet(`claim:${claimId}`, claimRes.value.claim);
        }
        if (citRes.status === "fulfilled") {
          setCitations(citRes.value);
        }
        if (impactRes.status === "fulfilled") {
          setImpact(impactRes.value);
        }
      } catch {
        // Use cached data if available
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [claimId]);

  return { claim, citations, impact, loading };
}
