import type { AppSettings, SummaryQualityStatus } from "../types";
import { DEFAULT_REQUEST_TIMEOUT_MS, normalizeActorRoleInput } from "../utils/appHelpers";

export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
export const DEFAULT_SITE_ID = "SITE-001";
export const DEFAULT_OPERATOR_ID = "OP-01";

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function normalizeSummaryQualityStatus(raw: unknown): SummaryQualityStatus {
  if (raw === "all" || raw === "valid" || raw === "repeat" || raw === "reject") {
    return raw;
  }
  return "valid";
}

export function buildDefaultAppSettings(apiKey: string): AppSettings {
  return {
    api_base_url: DEFAULT_API_BASE_URL,
    api_key: apiKey,
    actor_role: "operator",
    site_id: DEFAULT_SITE_ID,
    operator_id: DEFAULT_OPERATOR_ID,
    summary_quality_status: "valid",
    summary_sync_id: "",
    request_timeout_ms: DEFAULT_REQUEST_TIMEOUT_MS,
  };
}

export function normalizeStoredAppSettings(
  rawSettings: unknown,
  secureApiKey: string,
): AppSettings | null {
  if (!rawSettings || typeof rawSettings !== "object") {
    return null;
  }
  const parsed = rawSettings as Record<string, unknown>;
  const apiBaseUrl = readString(parsed.api_base_url).trim();
  const requestTimeoutMs = readString(parsed.request_timeout_ms).trim();

  return {
    api_base_url: apiBaseUrl || DEFAULT_API_BASE_URL,
    api_key: secureApiKey || readString(parsed.api_key),
    actor_role: normalizeActorRoleInput(readString(parsed.actor_role) || "operator"),
    site_id: readString(parsed.site_id) || DEFAULT_SITE_ID,
    operator_id: readString(parsed.operator_id) || DEFAULT_OPERATOR_ID,
    summary_quality_status: normalizeSummaryQualityStatus(parsed.summary_quality_status),
    summary_sync_id: readString(parsed.summary_sync_id),
    request_timeout_ms: requestTimeoutMs || DEFAULT_REQUEST_TIMEOUT_MS,
  };
}

export function parseStoredAppSettings(
  rawSettingsJson: string | null,
  secureApiKey: string,
): AppSettings | null {
  if (!rawSettingsJson) {
    return secureApiKey ? buildDefaultAppSettings(secureApiKey) : null;
  }

  try {
    return normalizeStoredAppSettings(JSON.parse(rawSettingsJson), secureApiKey);
  } catch {
    return null;
  }
}

export function buildPlainStoredAppSettings(settings: AppSettings): AppSettings {
  return {
    ...settings,
    api_key: "",
  };
}
