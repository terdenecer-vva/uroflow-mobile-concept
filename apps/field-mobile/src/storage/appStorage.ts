import AsyncStorage from "@react-native-async-storage/async-storage";
import * as SecureStore from "expo-secure-store";
import type { AppSettings, PendingSubmission } from "../types";
import {
  buildPlainStoredAppSettings,
  parseStoredAppSettings,
} from "./appSettingsStorage";
import { normalizePendingSubmission } from "./pendingSubmissionStorage";

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
  return parseStoredAppSettings(raw, secureApiKey);
}

export async function saveAppSettings(settings: AppSettings): Promise<void> {
  await AsyncStorage.setItem(APP_SETTINGS_KEY, JSON.stringify(buildPlainStoredAppSettings(settings)));
  try {
    await SecureStore.setItemAsync(APP_SETTINGS_API_KEY_SECURE_KEY, settings.api_key);
  } catch {
    await AsyncStorage.setItem(APP_SETTINGS_KEY, JSON.stringify(settings));
  }
}
