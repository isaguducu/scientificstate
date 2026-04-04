import { createClient, Session } from "@supabase/supabase-js";
import AsyncStorage from "@react-native-async-storage/async-storage";

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || "";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

/** Sign in with ORCID via Supabase OAuth. */
export async function signInWithOrcid(): Promise<void> {
  await supabase.auth.signInWithOAuth({
    provider: "orcid" as never, // ORCID is a custom provider
    options: {
      redirectTo: "scientificstate://auth/callback",
    },
  });
}

/** Sign out and clear session. */
export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}

/** Get current session (null if not authenticated). */
export async function getSession(): Promise<Session | null> {
  const { data } = await supabase.auth.getSession();
  return data.session;
}

/** Get access token for API calls. */
export async function getAccessToken(): Promise<string | null> {
  const session = await getSession();
  return session?.access_token ?? null;
}

/** Listen for auth state changes. */
export function onAuthStateChange(
  callback: (session: Session | null) => void,
): { unsubscribe: () => void } {
  const { data } = supabase.auth.onAuthStateChange((_event, session) => {
    callback(session);
  });
  return { unsubscribe: data.subscription.unsubscribe };
}
