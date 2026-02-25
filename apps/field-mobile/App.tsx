import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import AsyncStorage from "@react-native-async-storage/async-storage";

type QualityStatus = "valid" | "repeat" | "reject";
type SummaryQualityStatus = QualityStatus | "all";

type ComparisonMetricSummary = {
  metric: string;
  paired_samples: number;
  mean_error: number | null;
  mean_absolute_error: number | null;
  rmse: number | null;
  pearson_r: number | null;
};

type ComparisonSummaryResponse = {
  records_considered: number;
  records_matched_filters: number;
  quality_distribution: Record<string, number>;
  metrics: ComparisonMetricSummary[];
};

type AuthContextResponse = {
  auth_result: string;
  actor_role: string | null;
  actor_site_id: string | null;
  actor_operator_id: string | null;
  cross_site_allowed: boolean;
};

type PairedPayload = {
  session: {
    session_id: string;
    sync_id: string | null;
    site_id: string;
    subject_id: string;
    operator_id: string;
    attempt_number: number | null;
    measured_at: string;
    platform: string;
    device_model: string | null;
    app_version: string | null;
    capture_mode: string;
  };
  app: {
    metrics: {
      qmax_ml_s: number | null;
      qavg_ml_s: number | null;
      vvoid_ml: number | null;
      flow_time_s: number | null;
      tqmax_s: number | null;
    };
    quality_status: QualityStatus;
    quality_score: number | null;
    model_id: string | null;
  };
  reference: {
    metrics: {
      qmax_ml_s: number | null;
      qavg_ml_s: number | null;
      vvoid_ml: number | null;
      flow_time_s: number | null;
      tqmax_s: number | null;
    };
    device_model: string | null;
    device_serial: string | null;
  };
  notes: string | null;
};

type PendingSubmission = {
  id: string;
  created_at: string;
  payload: PairedPayload;
  request_headers: RequestHeaderContext;
  attempt_count: number;
  last_attempt_at: string | null;
  last_error: string | null;
  last_status_code: number | null;
};

type AppSettings = {
  api_base_url: string;
  api_key: string;
  actor_role: string;
  site_id: string;
  operator_id: string;
  summary_quality_status: SummaryQualityStatus;
  summary_sync_id: string;
  request_timeout_ms: string;
};

type SubmitAttemptResult = {
  ok: boolean;
  statusCode: number | null;
  body: string;
  retryable: boolean;
};

type RequestHeaderContext = {
  api_key: string;
  actor_role: string;
  site_id: string;
  operator_id: string;
};

const PENDING_SUBMISSIONS_KEY = "uroflow_pending_submissions_v1";
const APP_SETTINGS_KEY = "uroflow_field_settings_v1";
const DEFAULT_REQUEST_TIMEOUT_MS = "15000";
const ALLOWED_ACTOR_ROLES = ["operator", "investigator", "data_manager", "admin"] as const;

const defaultMeasuredAt = new Date().toISOString().slice(0, 19) + "Z";

function parseNumber(value: string): number | null {
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

function createSessionId(): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  const h = String(now.getUTCHours()).padStart(2, "0");
  const min = String(now.getUTCMinutes()).padStart(2, "0");
  const s = String(now.getUTCSeconds()).padStart(2, "0");
  return `SESSION-${y}${m}${d}-${h}${min}${s}`;
}

function createSyncId(): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  const h = String(now.getUTCHours()).padStart(2, "0");
  const min = String(now.getUTCMinutes()).padStart(2, "0");
  const s = String(now.getUTCSeconds()).padStart(2, "0");
  const randomPart = Math.random().toString(36).slice(2, 8).toUpperCase();
  return `SYNC-${y}${m}${d}-${h}${min}${s}-${randomPart}`;
}

function formatNullable(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(3);
}

function createPendingId(): string {
  const randomPart = Math.random().toString(36).slice(2, 10);
  return `PENDING-${Date.now()}-${randomPart}`;
}

function classifyRetryable(statusCode: number | null): boolean {
  if (statusCode == null) {
    return true;
  }
  if (statusCode >= 500) {
    return true;
  }
  return statusCode === 408 || statusCode === 425 || statusCode === 429;
}

function normalizeActorRoleInput(rawValue: string | null | undefined): string {
  const normalized = (rawValue ?? "").trim().toLowerCase();
  if (ALLOWED_ACTOR_ROLES.includes(normalized as (typeof ALLOWED_ACTOR_ROLES)[number])) {
    return normalized;
  }
  return "operator";
}

function buildHeaderContextFromValues(
  apiKey: string,
  actorRole: string,
  siteId: string,
  operatorId: string,
): RequestHeaderContext {
  return {
    api_key: apiKey.trim(),
    actor_role: normalizeActorRoleInput(actorRole),
    site_id: siteId.trim(),
    operator_id: operatorId.trim(),
  };
}

function normalizeRequestHeaderContext(
  raw: unknown,
  payload: PairedPayload,
): RequestHeaderContext {
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

function clampTimeoutMs(rawValue: string): number {
  const parsed = Number(rawValue);
  if (!Number.isFinite(parsed)) {
    return 15000;
  }
  return Math.min(120000, Math.max(2000, Math.round(parsed)));
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
    typeof candidate.id === "string" && candidate.id.trim()
      ? candidate.id
      : createPendingId();
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
    payload: payload as PairedPayload,
    request_headers: normalizeRequestHeaderContext(candidate.request_headers, payload as PairedPayload),
    attempt_count: attemptCount,
    last_attempt_at:
      typeof candidate.last_attempt_at === "string" ? candidate.last_attempt_at : null,
    last_error: typeof candidate.last_error === "string" ? candidate.last_error : null,
    last_status_code:
      typeof candidate.last_status_code === "number"
        ? candidate.last_status_code
        : null,
  };
}

async function loadPendingSubmissions(): Promise<PendingSubmission[]> {
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

async function savePendingSubmissions(queue: PendingSubmission[]): Promise<void> {
  await AsyncStorage.setItem(PENDING_SUBMISSIONS_KEY, JSON.stringify(queue));
}

async function loadAppSettings(): Promise<AppSettings | null> {
  const raw = await AsyncStorage.getItem(APP_SETTINGS_KEY);
  if (!raw) {
    return null;
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
      api_key: typeof parsed.api_key === "string" ? parsed.api_key : "",
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

async function saveAppSettings(settings: AppSettings): Promise<void> {
  await AsyncStorage.setItem(APP_SETTINGS_KEY, JSON.stringify(settings));
}

export default function App() {
  const defaultPlatform = Platform.OS === "ios" ? "ios" : "android";

  const [apiBaseUrl, setApiBaseUrl] = useState("http://127.0.0.1:8000");
  const [apiKey, setApiKey] = useState("");
  const [actorRole, setActorRole] = useState("operator");
  const [requestTimeoutMs, setRequestTimeoutMs] = useState(DEFAULT_REQUEST_TIMEOUT_MS);
  const [sessionId, setSessionId] = useState(createSessionId());
  const [syncId, setSyncId] = useState(createSyncId());
  const [siteId, setSiteId] = useState("SITE-001");
  const [subjectId, setSubjectId] = useState("SUBJ-001");
  const [operatorId, setOperatorId] = useState("OP-01");
  const [attemptNumber, setAttemptNumber] = useState("1");
  const [measuredAt, setMeasuredAt] = useState(defaultMeasuredAt);
  const [platform, setPlatform] = useState(defaultPlatform);
  const [deviceModel, setDeviceModel] = useState(Platform.OS);
  const [appVersion, setAppVersion] = useState("0.1.0");
  const [captureMode, setCaptureMode] = useState("water_impact");

  const [appQmax, setAppQmax] = useState("");
  const [appQavg, setAppQavg] = useState("");
  const [appVvoid, setAppVvoid] = useState("");
  const [appFlowTime, setAppFlowTime] = useState("");
  const [appTqmax, setAppTqmax] = useState("");
  const [appQualityStatus, setAppQualityStatus] = useState<QualityStatus>("valid");
  const [appQualityScore, setAppQualityScore] = useState("");
  const [appModelId, setAppModelId] = useState("fusion-v0.1");

  const [refQmax, setRefQmax] = useState("");
  const [refQavg, setRefQavg] = useState("");
  const [refVvoid, setRefVvoid] = useState("");
  const [refFlowTime, setRefFlowTime] = useState("");
  const [refTqmax, setRefTqmax] = useState("");
  const [refDeviceModel, setRefDeviceModel] = useState("");
  const [refDeviceSerial, setRefDeviceSerial] = useState("");

  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastResponse, setLastResponse] = useState<string>("");
  const [pendingQueue, setPendingQueue] = useState<PendingSubmission[]>([]);
  const [syncingPending, setSyncingPending] = useState(false);
  const [syncStatusMessage, setSyncStatusMessage] = useState("");
  const [summaryQualityStatus, setSummaryQualityStatus] = useState<SummaryQualityStatus>("valid");
  const [summarySyncId, setSummarySyncId] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [summary, setSummary] = useState<ComparisonSummaryResponse | null>(null);
  const [settingsHydrated, setSettingsHydrated] = useState(false);

  const payload = useMemo<PairedPayload>(() => {
    return {
      session: {
        session_id: sessionId.trim(),
        sync_id: syncId.trim() || null,
        site_id: siteId.trim(),
        subject_id: subjectId.trim(),
        operator_id: operatorId.trim(),
        attempt_number: parseNumber(attemptNumber),
        measured_at: measuredAt.trim(),
        platform,
        device_model: deviceModel.trim() || null,
        app_version: appVersion.trim() || null,
        capture_mode: captureMode,
      },
      app: {
        metrics: {
          qmax_ml_s: parseNumber(appQmax),
          qavg_ml_s: parseNumber(appQavg),
          vvoid_ml: parseNumber(appVvoid),
          flow_time_s: parseNumber(appFlowTime),
          tqmax_s: parseNumber(appTqmax),
        },
        quality_status: appQualityStatus,
        quality_score: parseNumber(appQualityScore),
        model_id: appModelId.trim() || null,
      },
      reference: {
        metrics: {
          qmax_ml_s: parseNumber(refQmax),
          qavg_ml_s: parseNumber(refQavg),
          vvoid_ml: parseNumber(refVvoid),
          flow_time_s: parseNumber(refFlowTime),
          tqmax_s: parseNumber(refTqmax),
        },
        device_model: refDeviceModel.trim() || null,
        device_serial: refDeviceSerial.trim() || null,
      },
      notes: notes.trim() || null,
    };
  }, [
    appFlowTime,
    appModelId,
    appQavg,
    appQmax,
    appQualityScore,
    appQualityStatus,
    appTqmax,
    appVersion,
    appVvoid,
    attemptNumber,
    captureMode,
    deviceModel,
    measuredAt,
    notes,
    operatorId,
    platform,
    refDeviceModel,
    refDeviceSerial,
    refFlowTime,
    refQavg,
    refQmax,
    refTqmax,
    refVvoid,
    sessionId,
    syncId,
    siteId,
    subjectId,
  ]);

  useEffect(() => {
    void (async () => {
      const [queue, settings] = await Promise.all([
        loadPendingSubmissions(),
        loadAppSettings(),
      ]);
      setPendingQueue(queue);
      if (settings) {
        setApiBaseUrl(settings.api_base_url);
        setApiKey(settings.api_key);
        setActorRole(settings.actor_role);
        setSiteId(settings.site_id);
        setOperatorId(settings.operator_id);
        setSummaryQualityStatus(settings.summary_quality_status);
        setSummarySyncId(settings.summary_sync_id);
        setRequestTimeoutMs(settings.request_timeout_ms);
      }
      setSettingsHydrated(true);
    })();
  }, []);

  useEffect(() => {
    if (!settingsHydrated) {
      return;
    }
    const settings: AppSettings = {
      api_base_url: apiBaseUrl,
      api_key: apiKey,
      actor_role: actorRole,
      site_id: siteId,
      operator_id: operatorId,
      summary_quality_status: summaryQualityStatus,
      summary_sync_id: summarySyncId,
      request_timeout_ms: requestTimeoutMs,
    };
    void saveAppSettings(settings);
  }, [
    actorRole,
    apiBaseUrl,
    apiKey,
    operatorId,
    requestTimeoutMs,
    settingsHydrated,
    siteId,
    summarySyncId,
    summaryQualityStatus,
  ]);

  async function persistPendingQueue(queue: PendingSubmission[]): Promise<void> {
    await savePendingSubmissions(queue);
    setPendingQueue(queue);
  }

  async function enqueuePendingSubmission(item: PendingSubmission): Promise<void> {
    const queue =
      pendingQueue.length > 0 ? [...pendingQueue] : await loadPendingSubmissions();
    queue.push(item);
    await persistPendingQueue(queue);
  }

  function createCurrentRequestHeaderContext(): RequestHeaderContext {
    return buildHeaderContextFromValues(apiKey, actorRole, siteId, operatorId);
  }

  function buildRequestHeaders(
    includeContentType: boolean,
    headerContext?: RequestHeaderContext,
  ): Record<string, string> {
    const context = headerContext ?? createCurrentRequestHeaderContext();
    const headers: Record<string, string> = {};
    if (includeContentType) {
      headers["Content-Type"] = "application/json";
    }
    if (context.api_key) {
      headers["x-api-key"] = context.api_key;
    }
    if (context.operator_id) {
      headers["x-operator-id"] = context.operator_id;
    }
    if (context.site_id) {
      headers["x-site-id"] = context.site_id;
    }
    if (context.actor_role) {
      headers["x-actor-role"] = context.actor_role;
    }
    headers["x-request-id"] = createPendingId();
    return headers;
  }

  async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
    const timeoutMs = clampTimeoutMs(requestTimeoutMs);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timeout);
    }
  }

  function resolvePendingHeaderContext(item: PendingSubmission): RequestHeaderContext {
    const current = createCurrentRequestHeaderContext();
    return {
      api_key: item.request_headers.api_key || current.api_key,
      actor_role: item.request_headers.actor_role || current.actor_role,
      site_id: item.request_headers.site_id || current.site_id,
      operator_id: item.request_headers.operator_id || current.operator_id,
    };
  }

  async function attemptSubmit(
    currentPayload: PairedPayload,
    headerContext?: RequestHeaderContext,
  ): Promise<SubmitAttemptResult> {
    const url = `${apiBaseUrl.replace(/\/$/, "")}/api/v1/paired-measurements`;
    try {
      const response = await fetchWithTimeout(url, {
        method: "POST",
        headers: buildRequestHeaders(true, headerContext),
        body: JSON.stringify(currentPayload),
      });
      const body = await response.text();
      return {
        ok: response.ok,
        statusCode: response.status,
        body,
        retryable: !response.ok ? classifyRetryable(response.status) : false,
      };
    } catch (error) {
      const message = String(error);
      return {
        ok: false,
        statusCode: null,
        body: message,
        retryable: true,
      };
    }
  }

  async function syncPendingSubmissions(): Promise<void> {
    setSyncingPending(true);
    setSyncStatusMessage("");
    try {
      const queue = await loadPendingSubmissions();
      if (queue.length === 0) {
        setPendingQueue([]);
        setSyncStatusMessage("Pending queue is empty.");
        return;
      }

      const remaining: PendingSubmission[] = [];
      let synced = 0;
      let droppedNonRetryable = 0;

      for (const item of queue) {
        const headerContext = resolvePendingHeaderContext(item);
        const result = await attemptSubmit(item.payload, headerContext);
        const attemptedItem: PendingSubmission = {
          ...item,
          request_headers: headerContext,
          attempt_count: item.attempt_count + 1,
          last_attempt_at: new Date().toISOString(),
          last_status_code: result.statusCode,
          last_error: result.ok ? null : result.body,
        };
        if (result.ok) {
          synced += 1;
          continue;
        }
        if (result.retryable) {
          remaining.push(attemptedItem);
          continue;
        }
        droppedNonRetryable += 1;
      }

      await persistPendingQueue(remaining);

      const statusMessage =
        `Sync completed. Synced: ${synced}, ` +
        `remaining retryable: ${remaining.length}, ` +
        `dropped non-retryable: ${droppedNonRetryable}.`;
      setSyncStatusMessage(statusMessage);
      setLastResponse(statusMessage);
      Alert.alert("Sync completed", statusMessage);
    } finally {
      setSyncingPending(false);
    }
  }

  async function clearPendingSubmissions(): Promise<void> {
    Alert.alert(
      "Clear pending queue",
      "Remove all pending submissions from local storage?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Clear",
          style: "destructive",
          onPress: () => {
            void persistPendingQueue([]);
            setSyncStatusMessage("Pending queue cleared.");
          },
        },
      ],
    );
  }

  async function testApiConnection(): Promise<void> {
    const baseUrl = apiBaseUrl.replace(/\/$/, "");
    const authContextUrl = `${baseUrl}/api/v1/auth-context`;
    try {
      const response = await fetchWithTimeout(authContextUrl, {
        method: "GET",
        headers: buildRequestHeaders(false),
      });
      if (response.status === 404) {
        const healthResponse = await fetchWithTimeout(`${baseUrl}/health`, {
          method: "GET",
          headers: buildRequestHeaders(false),
        });
        if (!healthResponse.ok) {
          setLastResponse(`Health check failed: HTTP ${healthResponse.status}`);
          Alert.alert("API check failed", `HTTP ${healthResponse.status}`);
          return;
        }
        setLastResponse("API reachable (health endpoint).");
        Alert.alert("API reachable", "Health check succeeded.");
        return;
      }
      if (!response.ok) {
        const body = await response.text();
        setLastResponse(`Auth-context check failed: HTTP ${response.status} ${body}`);
        Alert.alert("API check failed", `HTTP ${response.status}`);
        return;
      }
      const body = await response.text();
      const authContext = JSON.parse(body) as AuthContextResponse;
      const message =
        `Auth context OK: auth=${authContext.auth_result}, ` +
        `role=${authContext.actor_role ?? "n/a"}, ` +
        `site=${authContext.actor_site_id ?? "n/a"}`;
      setLastResponse(message);
      Alert.alert("API reachable", message);
    } catch (error) {
      const message = String(error);
      setLastResponse(`API check failed: ${message}`);
      Alert.alert("API check failed", message);
    }
  }

  function validateRequired(): string | null {
    if (!payload.session.session_id) {
      return "session_id is required";
    }
    if (!payload.session.site_id || !payload.session.subject_id || !payload.session.operator_id) {
      return "site_id, subject_id, operator_id are required";
    }
    if (!payload.session.attempt_number || payload.session.attempt_number < 1) {
      return "attempt_number must be >= 1";
    }
    if (!payload.session.measured_at) {
      return "measured_at is required";
    }
    if (payload.app.metrics.qmax_ml_s == null || payload.app.metrics.qavg_ml_s == null || payload.app.metrics.vvoid_ml == null) {
      return "App metrics qmax/qavg/vvoid are required";
    }
    if (payload.reference.metrics.qmax_ml_s == null || payload.reference.metrics.qavg_ml_s == null || payload.reference.metrics.vvoid_ml == null) {
      return "Reference metrics qmax/qavg/vvoid are required";
    }
    return null;
  }

  async function submitPayload() {
    const validationError = validateRequired();
    if (validationError) {
      Alert.alert("Validation", validationError);
      return;
    }

    setSubmitting(true);
    setLastResponse("");

    try {
      const requestHeaderContext = createCurrentRequestHeaderContext();
      const result = await attemptSubmit(payload, requestHeaderContext);
      if (result.ok) {
        setLastResponse(result.body);
        Alert.alert("Submitted", "Paired measurement uploaded");
        setSessionId(createSessionId());
        setSyncId(createSyncId());
        return;
      }

      if (!result.retryable) {
        const nonRetryableMessage =
          `Upload rejected and not queued. ` +
          `${result.statusCode ? `HTTP ${result.statusCode}` : "ERROR"} ${result.body}`;
        setLastResponse(nonRetryableMessage);
        Alert.alert(
          "Upload rejected",
          "Request is non-retryable. Check payload, API key, and required fields.",
        );
        return;
      }

      const pendingItem: PendingSubmission = {
        id: createPendingId(),
        created_at: new Date().toISOString(),
        payload,
        request_headers: requestHeaderContext,
        attempt_count: 0,
        last_attempt_at: null,
        last_error: result.body,
        last_status_code: result.statusCode,
      };
      await enqueuePendingSubmission(pendingItem);
      setLastResponse(
        `Queued for retry. Last error: ${
          result.statusCode ? `HTTP ${result.statusCode}` : "NETWORK"
        } ${result.body}`
      );
      Alert.alert(
        "Saved offline",
        "No successful upload now. Record added to pending queue.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function loadComparisonSummary() {
    const baseUrl = apiBaseUrl.replace(/\/$/, "");
    const params = new URLSearchParams();
    if (siteId.trim()) {
      params.set("site_id", siteId.trim());
    }
    if (summarySyncId.trim()) {
      params.set("sync_id", summarySyncId.trim());
    }
    params.set("quality_status", summaryQualityStatus);
    const url = `${baseUrl}/api/v1/comparison-summary?${params.toString()}`;

    setSummaryLoading(true);
    setSummaryError("");

    try {
      const response = await fetchWithTimeout(url, {
        method: "GET",
        headers: buildRequestHeaders(false),
      });
      const body = await response.text();
      if (!response.ok) {
        setSummary(null);
        setSummaryError(`HTTP ${response.status}: ${body}`);
        return;
      }
      setSummary(JSON.parse(body) as ComparisonSummaryResponse);
    } catch (error) {
      setSummary(null);
      setSummaryError(String(error));
    } finally {
      setSummaryLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Uroflow Field Capture</Text>
        <Text style={styles.subtitle}>Pair app result with reference uroflowmeter</Text>

        <Text style={styles.sectionTitle}>API</Text>
        <LabeledInput label="API Base URL" value={apiBaseUrl} onChangeText={setApiBaseUrl} />
        <LabeledInput
          label="API Key (x-api-key)"
          value={apiKey}
          onChangeText={setApiKey}
          secureTextEntry
        />
        <LabeledInput
          label="Actor Role (x-actor-role)"
          value={actorRole}
          onChangeText={(value) => setActorRole(normalizeActorRoleInput(value))}
        />
        <LabeledInput
          label="Request Timeout (ms)"
          value={requestTimeoutMs}
          onChangeText={setRequestTimeoutMs}
          keyboardType="number-pad"
        />
        <View style={styles.pendingRow}>
          <Text style={styles.pendingText}>Pending submissions: {pendingQueue.length}</Text>
        </View>
        {pendingQueue.slice(0, 3).map((item) => (
          <Text key={item.id} style={styles.pendingItemText}>
            {item.id}: attempts={item.attempt_count}
            {item.payload.session.sync_id ? `, sync=${item.payload.session.sync_id}` : ""}
            {item.request_headers.site_id ? `, site=${item.request_headers.site_id}` : ""}
            {item.request_headers.actor_role ? `, role=${item.request_headers.actor_role}` : ""}
            {item.last_status_code != null ? `, last_status=${item.last_status_code}` : ""}
            {item.last_error ? `, last_error=${item.last_error.slice(0, 80)}` : ""}
          </Text>
        ))}
        {pendingQueue.length > 3 ? (
          <Text style={styles.pendingItemText}>
            ...and {pendingQueue.length - 3} more pending submissions
          </Text>
        ) : null}
        <View style={styles.buttonRow}>
          <Pressable
            style={[styles.summaryButton, styles.buttonGrow]}
            onPress={() => void testApiConnection()}
          >
            <Text style={styles.submitButtonText}>Test API</Text>
          </Pressable>
          <Pressable
            style={[
              styles.summaryButton,
              styles.buttonGrow,
              syncingPending && styles.submitButtonDisabled,
            ]}
            onPress={() => void syncPendingSubmissions()}
            disabled={syncingPending}
          >
            <Text style={styles.submitButtonText}>
              {syncingPending ? "Syncing..." : "Sync Queue"}
            </Text>
          </Pressable>
          <Pressable
            style={[styles.dangerButton, styles.buttonGrow]}
            onPress={() => void clearPendingSubmissions()}
          >
            <Text style={styles.submitButtonText}>Clear Queue</Text>
          </Pressable>
        </View>
        {syncStatusMessage ? (
          <Text style={styles.syncStatusText}>{syncStatusMessage}</Text>
        ) : null}

        <Text style={styles.sectionTitle}>Session</Text>
        <LabeledInput label="Session ID" value={sessionId} onChangeText={setSessionId} />
        <LabeledInput label="Sync ID" value={syncId} onChangeText={setSyncId} />
        <LabeledInput label="Site ID" value={siteId} onChangeText={setSiteId} />
        <LabeledInput label="Subject ID" value={subjectId} onChangeText={setSubjectId} />
        <LabeledInput label="Operator ID" value={operatorId} onChangeText={setOperatorId} />
        <LabeledInput label="Attempt Number" value={attemptNumber} onChangeText={setAttemptNumber} keyboardType="number-pad" />
        <LabeledInput label="Measured At (ISO)" value={measuredAt} onChangeText={setMeasuredAt} />
        <LabeledInput label="Platform (ios/android)" value={platform} onChangeText={setPlatform} />
        <LabeledInput label="Device Model" value={deviceModel} onChangeText={setDeviceModel} />
        <LabeledInput label="App Version" value={appVersion} onChangeText={setAppVersion} />
        <LabeledInput label="Capture Mode" value={captureMode} onChangeText={setCaptureMode} />

        <Text style={styles.sectionTitle}>App Measurement</Text>
        <LabeledInput label="Qmax (ml/s)" value={appQmax} onChangeText={setAppQmax} keyboardType="decimal-pad" />
        <LabeledInput label="Qavg (ml/s)" value={appQavg} onChangeText={setAppQavg} keyboardType="decimal-pad" />
        <LabeledInput label="Vvoid (ml)" value={appVvoid} onChangeText={setAppVvoid} keyboardType="decimal-pad" />
        <LabeledInput label="Flow Time (s)" value={appFlowTime} onChangeText={setAppFlowTime} keyboardType="decimal-pad" />
        <LabeledInput label="TQmax (s)" value={appTqmax} onChangeText={setAppTqmax} keyboardType="decimal-pad" />
        <LabeledInput label="Quality Status" value={appQualityStatus} onChangeText={(value) => setAppQualityStatus((value as QualityStatus) || "valid")} />
        <LabeledInput label="Quality Score (0-100)" value={appQualityScore} onChangeText={setAppQualityScore} keyboardType="decimal-pad" />
        <LabeledInput label="Model ID" value={appModelId} onChangeText={setAppModelId} />

        <Text style={styles.sectionTitle}>Reference Uroflowmeter</Text>
        <LabeledInput label="Qmax (ml/s)" value={refQmax} onChangeText={setRefQmax} keyboardType="decimal-pad" />
        <LabeledInput label="Qavg (ml/s)" value={refQavg} onChangeText={setRefQavg} keyboardType="decimal-pad" />
        <LabeledInput label="Vvoid (ml)" value={refVvoid} onChangeText={setRefVvoid} keyboardType="decimal-pad" />
        <LabeledInput label="Flow Time (s)" value={refFlowTime} onChangeText={setRefFlowTime} keyboardType="decimal-pad" />
        <LabeledInput label="TQmax (s)" value={refTqmax} onChangeText={setRefTqmax} keyboardType="decimal-pad" />
        <LabeledInput label="Reference Device Model" value={refDeviceModel} onChangeText={setRefDeviceModel} />
        <LabeledInput label="Reference Device Serial" value={refDeviceSerial} onChangeText={setRefDeviceSerial} />

        <Text style={styles.sectionTitle}>Notes</Text>
        <LabeledInput label="Notes" value={notes} onChangeText={setNotes} multiline />

        <Pressable style={[styles.submitButton, submitting && styles.submitButtonDisabled]} onPress={submitPayload} disabled={submitting}>
          <Text style={styles.submitButtonText}>{submitting ? "Submitting..." : "Submit Paired Measurement"}</Text>
        </Pressable>

        <Text style={styles.sectionTitle}>Last API Response</Text>
        <View style={styles.responseBox}>
          <Text style={styles.responseText}>{lastResponse || "No response yet"}</Text>
        </View>

        <Text style={styles.sectionTitle}>Comparison Summary (App vs Reference)</Text>
        <LabeledInput
          label="Summary Quality Status (valid/repeat/reject/all)"
          value={summaryQualityStatus}
          onChangeText={(value) =>
            setSummaryQualityStatus((value as SummaryQualityStatus) || "valid")
          }
        />
        <LabeledInput
          label="Summary Sync ID (optional)"
          value={summarySyncId}
          onChangeText={setSummarySyncId}
        />
        <Pressable
          style={[styles.summaryButton, summaryLoading && styles.submitButtonDisabled]}
          onPress={loadComparisonSummary}
          disabled={summaryLoading}
        >
          <Text style={styles.submitButtonText}>
            {summaryLoading ? "Loading..." : "Load Comparison Summary"}
          </Text>
        </Pressable>
        {summaryError ? (
          <Text style={styles.summaryErrorText}>{summaryError}</Text>
        ) : null}
        <View style={styles.responseBox}>
          {summary ? (
            <>
              <Text style={styles.summaryText}>
                Records considered: {summary.records_considered} / {summary.records_matched_filters}
              </Text>
              <Text style={styles.summaryText}>
                Quality distribution: valid={summary.quality_distribution.valid ?? 0} repeat=
                {summary.quality_distribution.repeat ?? 0} reject=
                {summary.quality_distribution.reject ?? 0}
              </Text>
              {summary.metrics.map((metric) => (
                <Text key={metric.metric} style={styles.summaryMetricText}>
                  {metric.metric}: n={metric.paired_samples}, MAE=
                  {formatNullable(metric.mean_absolute_error)}, bias=
                  {formatNullable(metric.mean_error)}, RMSE={formatNullable(metric.rmse)}, r=
                  {formatNullable(metric.pearson_r)}
                </Text>
              ))}
            </>
          ) : (
            <Text style={styles.responseText}>No summary loaded yet</Text>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

type InputProps = {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  keyboardType?: "default" | "number-pad" | "decimal-pad";
  multiline?: boolean;
  secureTextEntry?: boolean;
};

function LabeledInput({
  label,
  value,
  onChangeText,
  keyboardType = "default",
  multiline = false,
  secureTextEntry = false,
}: InputProps) {
  return (
    <View style={styles.inputWrap}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && styles.multilineInput]}
        value={value}
        onChangeText={onChangeText}
        keyboardType={keyboardType}
        multiline={multiline}
        secureTextEntry={secureTextEntry}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f6f7f8",
  },
  container: {
    padding: 16,
    paddingBottom: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: "#15202b",
  },
  subtitle: {
    marginTop: 4,
    marginBottom: 16,
    color: "#475467",
  },
  sectionTitle: {
    marginTop: 14,
    marginBottom: 8,
    fontSize: 16,
    fontWeight: "600",
    color: "#111827",
  },
  inputWrap: {
    marginBottom: 8,
  },
  label: {
    marginBottom: 4,
    fontSize: 13,
    color: "#334155",
  },
  input: {
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 8,
    backgroundColor: "#ffffff",
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
    color: "#111827",
  },
  multilineInput: {
    minHeight: 70,
    textAlignVertical: "top",
  },
  submitButton: {
    marginTop: 16,
    borderRadius: 10,
    backgroundColor: "#0f766e",
    paddingVertical: 12,
    alignItems: "center",
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitButtonText: {
    color: "#ffffff",
    fontWeight: "600",
  },
  responseBox: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: "#d1d5db",
    backgroundColor: "#ffffff",
    borderRadius: 8,
    padding: 10,
    minHeight: 80,
  },
  responseText: {
    color: "#0f172a",
    fontSize: 12,
  },
  summaryButton: {
    marginTop: 8,
    borderRadius: 10,
    backgroundColor: "#1f4f97",
    paddingVertical: 12,
    alignItems: "center",
  },
  dangerButton: {
    marginTop: 8,
    borderRadius: 10,
    backgroundColor: "#b91c1c",
    paddingVertical: 12,
    alignItems: "center",
  },
  buttonRow: {
    marginTop: 8,
    flexDirection: "row",
    gap: 8,
  },
  buttonGrow: {
    flex: 1,
  },
  summaryErrorText: {
    marginTop: 8,
    color: "#b91c1c",
    fontSize: 12,
  },
  pendingRow: {
    marginTop: 8,
    marginBottom: 4,
  },
  pendingText: {
    color: "#0f172a",
    fontSize: 13,
    fontWeight: "500",
  },
  pendingItemText: {
    color: "#334155",
    fontSize: 12,
    marginTop: 2,
  },
  syncStatusText: {
    marginTop: 8,
    color: "#0f172a",
    fontSize: 12,
  },
  summaryText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 6,
  },
  summaryMetricText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 4,
  },
});
