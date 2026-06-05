import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import type { AppSettings, PendingSubmission, SummaryQualityStatus } from "../types";
import { normalizePendingSubmission } from "./pendingSubmissionStorage";
import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  normalizeActorRoleInput,
} from "../utils/appHelpers";

const PENDING_SUBMISSIONS_KEY = "uroflow_pending_submissions_v1";
const APP_SETTINGS_KEY = "uroflow_field_settings_v1";
const APP_SETTINGS_API_KEY_SECURE_KEY = "uroflow_field_api_key_secure_v1";

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
