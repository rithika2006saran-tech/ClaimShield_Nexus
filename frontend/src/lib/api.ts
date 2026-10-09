import { supabase } from "./supabase";

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token || "";
  const r = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }, ...init });
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
    throw new Error(`${r.status}: ${msg}`);
  }
  return r.json();
}
export const post = <T = any>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });
