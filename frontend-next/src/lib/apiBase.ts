export function getApiBaseUrl(fallback: string = "http://127.0.0.1:8000"): string {
  // In the browser, always prefer the current origin.
  // This avoids mixed-content issues (https site calling http API) and avoids baking the wrong host
  // into the frontend build.
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }

  // On the server (or during build), fall back to configured env.
  const env = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (env && String(env).trim().length > 0) {
    return String(env).replace(/\/$/, "");
  }

  return fallback.replace(/\/$/, "");
}
