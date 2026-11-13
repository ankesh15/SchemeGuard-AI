export interface ErrorDetail {
  location: (string | number)[];
  message: string;
  type: string;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details: ErrorDetail[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const base =
    typeof window === "undefined"
      ? process.env.INTERNAL_API_URL || "http://localhost:8000"
      : "";
  const response = await fetch(`${base.replace(/\/$/, "")}${path}`, {
    ...options,
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      body.error?.message || "The service is unavailable. Please try again.",
      body.error?.details || [],
    );
  }
  return response.json() as Promise<T>;
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}
