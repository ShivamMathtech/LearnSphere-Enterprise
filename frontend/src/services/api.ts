import axios, { AxiosError } from "axios";
import type { AuthResult } from "../types/domain";
let accessToken = "";
let institution = "";
let refreshPromise: Promise<AuthResult> | null = null;
export const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  timeout: 30000,
});
export function setToken(token: string) {
  accessToken = token;
}
export function setInstitution(value: string) {
  institution = value;
}
function csrf() {
  return (
    document.cookie
      .split("; ")
      .find((v) => v.startsWith("ls_csrf="))
      ?.split("=")[1] || ""
  );
}
api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  if (institution) config.headers["X-Institution-ID"] = institution;
  config.headers["X-CSRF-Token"] = csrf();
  return config;
});
export async function refreshSession(): Promise<AuthResult> {
  if (!refreshPromise)
    refreshPromise = api
      .post<AuthResult>("/auth/refresh")
      .then((r) => {
        setToken(r.data.access_token);
        return r.data;
      })
      .finally(() => {
        refreshPromise = null;
      });
  return refreshPromise;
}
api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const config = error.config;
    if (
      error.response?.status === 401 &&
      config &&
      !config.url?.startsWith("/auth/") &&
      !config.headers["X-Retried"]
    ) {
      config.headers["X-Retried"] = "1";
      try {
        await refreshSession();
        return api(config);
      } catch {
        setToken("");
        window.dispatchEvent(new Event("session-expired"));
      }
    }
    return Promise.reject(error);
  },
);
export const get = async <T>(path: string): Promise<T> =>
  (await api.get<T>(path)).data;
export async function send<T = unknown>(
  path: string,
  body?: unknown,
  method = "POST",
): Promise<T> {
  return (await api.request<T>({ url: path, method, data: body })).data;
}
export function errorText(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail: unknown = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail))
      return detail
        .map(
          (x: { loc?: string[]; msg?: string }) =>
            `${x.loc?.slice(1).join(".")}: ${x.msg}`,
        )
        .join(" · ");
    if (detail && typeof detail === "object" && "message" in detail)
      return (
        String(detail.message) +
        ("remaining" in detail ? ": " + String(detail.remaining) : "")
      );
    return error.response
      ? `Request failed (${error.response.status})`
      : "Cannot reach the server. Check your connection and try again.";
  }
  return error instanceof Error ? error.message : "Something went wrong";
}
export async function download(path: string, filename: string, body?: unknown) {
  const response = await api.request<Blob>({
    url: path,
    method: body ? "POST" : "GET",
    data: body,
    responseType: "blob",
  });
  const url = URL.createObjectURL(response.data);
  const a = document.createElement("a");
  a.href = url;
  const disposition = String(response.headers["content-disposition"] || "");
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="([^"]+)"/i)?.[1];
  let suggested = plain || filename;
  if (encoded) {
    try { suggested = decodeURIComponent(encoded); } catch { suggested = filename; }
  }
  a.download = suggested.split(/[\\/]/).pop() || filename;
  a.click();
  URL.revokeObjectURL(url);
}
export async function upload(
  courseId: string,
  file: File,
  purpose: "resource" | "submission",
) {
  const body = new FormData();
  body.append("course_id", courseId);
  body.append("purpose", purpose);
  body.append("file", file);
  return (await api.post<{ id: string; name: string }>("/files", body)).data;
}
