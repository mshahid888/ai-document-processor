// Tiny API client: same-origin /api (proxied to the FastAPI backend),
// JWT from localStorage. 401 -> back to /login.

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("adp_token");
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem("adp_token", t);
  else localStorage.removeItem("adp_token");
}

export async function api(path: string, opts: RequestInit = {}): Promise<any> {
  const headers: Record<string, string> = { ...(opts.headers as any) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    setToken(null);
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
  }
  const ct = res.headers.get("content-type") || "";
  if (!res.ok) {
    const body = ct.includes("json") ? await res.json().catch(() => ({})) : {};
    throw new Error((body as any).detail || `Request failed (${res.status})`);
  }
  return ct.includes("json") ? res.json() : res.blob();
}

export async function downloadXlsx(path: string, filename: string) {
  const blob = (await api(path)) as Blob;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
