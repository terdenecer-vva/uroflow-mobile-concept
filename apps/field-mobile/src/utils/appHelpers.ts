import type {
  PairedPayload,
  PendingEndpoint,
  PendingSubmission,
  RequestHeaderContext,
} from "../types";

export const DEFAULT_REQUEST_TIMEOUT_MS = "15000";
export const COVERAGE_GOAL_RATIO = 0.9;

const ALLOWED_ACTOR_ROLES = ["operator", "investigator", "data_manager", "admin"] as const;

export function parseNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
}

function buildTimestampToken(): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  const h = String(now.getUTCHours()).padStart(2, "0");
  const min = String(now.getUTCMinutes()).padStart(2, "0");
  const s = String(now.getUTCSeconds()).padStart(2, "0");
  return `${y}${m}${d}-${h}${min}${s}`;
}

export function createSessionId(): string {
  return `SESSION-${buildTimestampToken()}`;
}

export function createSyncId(): string {
  const randomPart = Math.random().toString(36).slice(2, 8).toUpperCase();
  return `SYNC-${buildTimestampToken()}-${randomPart}`;
}

export function formatNullable(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(3);
}

export function createPendingId(): string {
  const randomPart = Math.random().toString(36).slice(2, 10);
  return `PENDING-${Date.now()}-${randomPart}`;
}

export function createRequestId(): string {
  return createPendingId();
}

export function classifyRetryable(statusCode: number | null): boolean {
  if (statusCode == null) {
    return true;
  }
  if (statusCode >= 500) {
    return true;
  }
  return statusCode === 408 || statusCode === 425 || statusCode === 429;
}

const SAFE_PENDING_ERROR_CATEGORIES = new Set([
  "network_or_timeout",
  "auth_or_permission",
  "validation",
  "server_or_client_response",
]);

export function summarizePendingError(error: string | null): string | null {
  if (!error) {
    return null;
  }
  const normalized = error.toLowerCase();
  if (SAFE_PENDING_ERROR_CATEGORIES.has(normalized)) {
    return normalized;
  }
  if (
    normalized.includes("abort") ||
    normalized.includes("network") ||
    normalized.includes("timed out") ||
    normalized.includes("failed to fetch")
  ) {
    return "network_or_timeout";
  }
  if (
    normalized.includes("unauthorized") ||
    normalized.includes("forbidden") ||
    normalized.includes("api key") ||
    normalized.includes("api_key") ||
    normalized.includes("apikey") ||
    normalized.includes("bearer") ||
    normalized.includes("token")
  ) {
    return "auth_or_permission";
  }
  if (
    normalized.includes("validation") ||
    normalized.includes("invalid") ||
    normalized.includes("field required") ||
    normalized.includes("unprocessable")
  ) {
    return "validation";
  }
  return "server_or_client_response";
}

export function formatSafeResponseProblem(
  statusCode: number | null,
  responseBody: string,
  fallbackStatusLabel: "ERROR" | "NETWORK" = "ERROR",
): string {
  const statusLabel = statusCode ? `HTTP ${statusCode}` : fallbackStatusLabel;
  return `${statusLabel} ${summarizePendingError(responseBody) ?? "server_or_client_response"}`;
}

export function summarizeSafeExceptionCategory(
  error: unknown,
  fallbackCategory: "network_or_timeout" | "server_or_client_response" = "server_or_client_response",
): string {
  const category = summarizePendingError(String(error)) ?? fallbackCategory;
  return category === "server_or_client_response" ? fallbackCategory : category;
}

export function formatSafeExceptionMessage(
  error: unknown,
  fallbackStatusLabel: "ERROR" | "NETWORK" = "ERROR",
): string {
  const fallbackCategory =
    fallbackStatusLabel === "NETWORK" ? "network_or_timeout" : "server_or_client_response";
  return `${fallbackStatusLabel} ${summarizeSafeExceptionCategory(error, fallbackCategory)}`;
}

export function normalizeActorRoleInput(rawValue: string | null | undefined): string {
  const normalized = (rawValue ?? "").trim().toLowerCase();
  if (ALLOWED_ACTOR_ROLES.includes(normalized as (typeof ALLOWED_ACTOR_ROLES)[number])) {
    return normalized;
  }
  return "operator";
}

export function buildHeaderContextFromValues(
  apiKey: string,
  actorRole: string,
  siteId: string,
  operatorId: string,
  requestId?: string,
): RequestHeaderContext {
  return {
    api_key: apiKey.trim(),
    actor_role: normalizeActorRoleInput(actorRole),
    site_id: siteId.trim(),
    operator_id: operatorId.trim(),
    request_id: requestId?.trim() || undefined,
  };
}

export function clampTimeoutMs(rawValue: string): number {
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) {
    return 15000;
  }
  return Math.min(120000, Math.max(2000, Math.round(parsed)));
}

export function normalizePendingEndpoint(raw: unknown): PendingEndpoint {
  if (raw === "capture_packages") {
    return "capture_packages";
  }
  return "paired_measurements";
}

export function extractCreatedRecordId(responseBody: string): number | null {
  try {
    const parsed = JSON.parse(responseBody) as { id?: unknown };
    return typeof parsed.id === "number" ? parsed.id : null;
  } catch {
    return null;
  }
}

export function runtimeCaptureMatchesSession(
  runtimePayload: Record<string, unknown> | null,
  session: PairedPayload["session"],
): boolean {
  if (!runtimePayload || typeof runtimePayload !== "object") {
    return false;
  }
  const sessionNode = runtimePayload.session;
  if (!sessionNode || typeof sessionNode !== "object") {
    return false;
  }
  const candidate = sessionNode as { session_id?: unknown; sync_id?: unknown };
  const sameSessionId =
    typeof candidate.session_id === "string" && candidate.session_id === session.session_id;
  const runtimeSyncId = typeof candidate.sync_id === "string" ? candidate.sync_id : null;
  const sessionSyncId = session.sync_id ?? null;
  return sameSessionId && runtimeSyncId === sessionSyncId;
}

export function resolvePendingHeaderContext(
  item: PendingSubmission,
  current: RequestHeaderContext,
): RequestHeaderContext {
  return {
    api_key: item.request_headers.api_key || current.api_key,
    actor_role: item.request_headers.actor_role || current.actor_role,
    site_id: item.request_headers.site_id || current.site_id,
    operator_id: item.request_headers.operator_id || current.operator_id,
    request_id: item.request_headers.request_id || item.id || current.request_id,
  };
}
