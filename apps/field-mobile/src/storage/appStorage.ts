import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import type { AppSettings, PendingSubmission, SummaryQualityStatus } from "../types";
import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  buildHeaderContextFromValues,
  createPendingId,
  normalizeActorRoleInput,
  normalizePendingEndpoint,
} from "../utils/appHelpers";

const PENDING_SUBMISSIONS_KEY = "uroflow_pending_submissions_v1";
const APP_SETTINGS_KEY = "uroflow_field_settings_v1";
const APP_SETTINGS_API_KEY_SECURE_KEY = "uroflow_field_api_key_secure_v1";

function normalizeRequestHeaderContext(
  raw: unknown,
  payload: { session: { site_id: string; operator_id: string } },
) {
  if (!raw || typeof raw !== "object") {
    return buildHeaderContextFromValues(
      "",
      "operator",
      payload.session.site_id ?? "",
      payload.session.operator_id ?? "",
    );
  }
  const candidate = raw as Record<string, unknown>;
  return buildHeaderContextFromValues(
    typeof candidate.api_key === "string" ? candidate.api_key : "",
    typeof candidate.actor_role === "string" ? candidate.actor_role : "operator",
    typeof candidate.site_id === "string" ? candidate.site_id : payload.session.site_id ?? "",
    typeof candidate.operator_id === "string"
      ? candidate.operator_id
      : payload.session.operator_id ?? "",
  );
}

function normalizePendingSubmission(raw: unknown): PendingSubmission | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const candidate = raw as Record<string, unknown>;
  const payload = candidate.payload;
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const id =
    typeof candidate.id === "string" && candidate.id.trim() ? candidate.id : createPendingId();
  const createdAt =
    typeof candidate.created_at === "string" && candidate.created_at.trim()
      ? candidate.created_at
      : new Date().toISOString();
  const attemptCountRaw = Number(candidate.attempt_count);
  const attemptCount = Number.isFinite(attemptCountRaw)
    ? Math.max(0, Math.round(attemptCountRaw))
    : 0;

  return {
    id,
    created_at: createdAt,
    endpoint: normalizePendingEndpoint(candidate.endpoint),
    payload: payload as PendingSubmission["payload"],
    request_headers: normalizeRequestHeaderContext(
      candidate.request_headers,
      payload as { session: { site_id: string; operator_id: string } },
    ),
    attempt_count: attemptCount,
    last_attempt_at: typeof candidate.last_attempt_at === "string" ? candidate.last_attempt_at : null,
    last_error: typeof candidate.last_error === "string" ? candidate.last_error : null,
    last_status_code:
      typeof candidate.last_status_code === "number" ? candidate.last_status_code : null,
  };
}

export async function loadPendingSubmissions(): Promise<PendingSubmission[]> {
  const raw = await AsyncStorage.getItem(PENDING_SUBMISSIONS_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .map((item) => normalizePendingSubmission(item))
      .filter((item): item is PendingSubmission => item != null);
  } catch {
    return [];
  }
}

export async function savePendingSubmissions(queue: PendingSubmission[]): Promise<void> {
  await AsyncStorage.setItem(PENDING_SUBMISSIONS_KEY, JSON.stringify(queue));
}

export async function loadAppSettings(): Promise<AppSettings | null> {
  const raw = await AsyncStorage.getItem(APP_SETTINGS_KEY);
  let secureApiKey = "";
  try {
    secureApiKey = (await SecureStore.getItemAsync(APP_SETTINGS_API_KEY_SECURE_KEY)) ?? "";
  } catch {
    secureApiKey = "";
  }
  if (!raw) {
    if (!secureApiKey) {
      return null;
    }
    return {
      api_base_url: "http://127.0.0.1:8000",
      api_key: secureApiKey,
      actor_role: "operator",
      site_id: "SITE-001",
      operator_id: "OP-01",
      summary_quality_status: "valid",
      summary_sync_id: "",
      request_timeout_ms: DEFAULT_REQUEST_TIMEOUT_MS,
    };
  }
  try {
    const parsed = JSON.parse(raw) as Partial<AppSettings>;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const summaryQualityStatus: SummaryQualityStatus =
      parsed.summary_quality_status === "all" ||
      parsed.summary_quality_status === "valid" ||
      parsed.summary_quality_status === "repeat" ||
      parsed.summary_quality_status === "reject"
        ? parsed.summary_quality_status
        : "valid";
    return {
      api_base_url:
        typeof parsed.api_base_url === "string" && parsed.api_base_url.trim()
          ? parsed.api_base_url
          : "http://127.0.0.1:8000",
      api_key: secureApiKey || (typeof parsed.api_key === "string" ? parsed.api_key : ""),
      actor_role: normalizeActorRoleInput(
        typeof parsed.actor_role === "string" ? parsed.actor_role : "operator",
      ),
      site_id: typeof parsed.site_id === "string" ? parsed.site_id : "SITE-001",
      operator_id: typeof parsed.operator_id === "string" ? parsed.operator_id : "OP-01",
      summary_quality_status: summaryQualityStatus,
      summary_sync_id: typeof parsed.summary_sync_id === "string" ? parsed.summary_sync_id : "",
      request_timeout_ms:
        typeof parsed.request_timeout_ms === "string" && parsed.request_timeout_ms.trim()
          ? parsed.request_timeout_ms
          : DEFAULT_REQUEST_TIMEOUT_MS,
    };
  } catch {
    return null;
  }
}

export async function saveAppSettings(settings: AppSettings): Promise<void> {
  const { api_key: apiKeyValue, ...plainSettings } = settings;
  await AsyncStorage.setItem(APP_SETTINGS_KEY, JSON.stringify({ ...plainSettings, api_key: "" }));
  try {
    await SecureStore.setItemAsync(APP_SETTINGS_API_KEY_SECURE_KEY, apiKeyValue);
  } catch {
    await AsyncStorage.setItem(APP_SETTINGS_KEY, JSON.stringify(settings));
  }
}
