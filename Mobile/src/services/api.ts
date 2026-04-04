const BASE_URL = process.env.EXPO_PUBLIC_API_URL || "https://scientificstate.org";

interface FetchOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: unknown;
  token?: string;
}

async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { method = "GET", headers = {}, body, token } = opts;

  const reqHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...headers,
  };
  if (token) {
    reqHeaders["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: reqHeaders,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// --- Discovery Feed ---

export interface EndorsedClaim {
  id: string;
  claim_id: string;
  ssv_id: string;
  domain_id: string;
  method_id: string;
  title: string;
  institution_id: string;
  researcher_orcid: string;
  gate_status: Record<string, boolean>;
  endorsed_at: string;
}

export interface FeedResponse {
  claims: EndorsedClaim[];
  total: number;
}

export function fetchFeed(token: string, limit = 50, offset = 0): Promise<FeedResponse> {
  return apiFetch(`/api/discover/feed?limit=${limit}&offset=${offset}`, { token });
}

export function fetchEndorsedClaims(params: {
  domain_id?: string;
  method_id?: string;
  limit?: number;
  offset?: number;
}): Promise<{ claims: EndorsedClaim[]; total: number }> {
  const qs = new URLSearchParams();
  if (params.domain_id) qs.set("domain_id", params.domain_id);
  if (params.method_id) qs.set("method_id", params.method_id);
  qs.set("limit", String(params.limit ?? 50));
  qs.set("offset", String(params.offset ?? 0));
  return apiFetch(`/api/discover/endorsed?${qs}`);
}

// --- Claim Detail ---

export interface CitationChain {
  cited_by: { claim_id: string; relationship: string }[];
  cites: { claim_id: string; relationship: string }[];
  cited_by_count: number;
  cites_count: number;
}

export interface ImpactScore {
  score: number;
  breakdown: {
    replication_count: number;
    citation_count: number;
    gate_completeness: number;
    institutional_diversity: number;
  };
  updated_at: string;
}

export function fetchClaimDetail(claimId: string): Promise<{ claim: EndorsedClaim }> {
  return apiFetch(`/api/discover/endorsed?claim_id=${encodeURIComponent(claimId)}`);
}

export function fetchCitations(claimId: string, depth = 3): Promise<CitationChain> {
  return apiFetch(`/api/discover/citations/${encodeURIComponent(claimId)}?depth=${depth}`);
}

export function fetchImpact(claimId: string): Promise<ImpactScore> {
  return apiFetch(`/api/discover/impact/${encodeURIComponent(claimId)}`);
}

// --- Researcher Profile ---

export interface ResearcherProfile {
  orcid: string;
  display_name: string;
  bio: string;
  research_areas: string[];
  endorsed_claims: EndorsedClaim[];
  impact_stats: { total_score: number; claim_count: number };
}

export function fetchProfile(orcid: string): Promise<ResearcherProfile> {
  return apiFetch(`/api/profile/${encodeURIComponent(orcid)}`);
}

// --- Collections ---

export interface Collection {
  id: string;
  author_orcid: string;
  title: string;
  description: string;
  claim_ids: string[];
  status: string;
  created_at: string;
}

export function fetchCollections(authorOrcid?: string, limit = 50): Promise<{ collections: Collection[] }> {
  const qs = new URLSearchParams();
  if (authorOrcid) qs.set("author_orcid", authorOrcid);
  qs.set("limit", String(limit));
  return apiFetch(`/api/collections?${qs}`);
}

// --- Push Token ---

export function registerPushToken(
  token: string,
  deviceToken: string,
  platform: "ios" | "android",
): Promise<void> {
  return apiFetch("/api/push/register", {
    method: "POST",
    token,
    body: { device_token: deviceToken, platform },
  });
}
