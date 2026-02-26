import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  AppState,
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
import { CameraView, useCameraPermissions } from "expo-camera";
import * as SecureStore from "expo-secure-store";
import {
  buildCaptureContractPayload,
  buildCaptureContractPayloadFromSamples,
} from "./src/capture/buildCaptureContract";
import {
  RuntimeCaptureSession,
  type RuntimeFlowPoint,
} from "./src/capture/runtimeCaptureSession";
import { estimateRoiSignalFromBase64 } from "./src/capture/roiSignalEstimator";

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

type CaptureCoverageSummaryResponse = {
  paired_total: number;
  paired_with_capture: number;
  paired_without_capture: number;
  coverage_ratio: number;
  quality_distribution: Record<string, number>;
  capture_match_distribution: Record<string, number>;
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

type CapturePackagePayload = {
  session: PairedPayload["session"];
  package_type: "capture_contract_json";
  capture_payload: Record<string, unknown>;
  paired_measurement_id: number | null;
  notes: string | null;
};

type PendingEndpoint = "paired_measurements" | "capture_packages";

type PendingSubmission = {
  id: string;
  created_at: string;
  endpoint: PendingEndpoint;
  payload: PairedPayload | CapturePackagePayload;
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

type RoiFrameAnalysisState = {
  prevHash: number | null;
  prevLength: number | null;
};

const PENDING_SUBMISSIONS_KEY = "uroflow_pending_submissions_v1";
const APP_SETTINGS_KEY = "uroflow_field_settings_v1";
const APP_SETTINGS_API_KEY_SECURE_KEY = "uroflow_field_api_key_secure_v1";
const DEFAULT_REQUEST_TIMEOUT_MS = "15000";
const COVERAGE_GOAL_RATIO = 0.9;
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
  payload: { session: { site_id: string; operator_id: string } },
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

function normalizePendingEndpoint(raw: unknown): PendingEndpoint {
  if (raw === "capture_packages") {
    return "capture_packages";
  }
  return "paired_measurements";
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
    endpoint: normalizePendingEndpoint(candidate.endpoint),
    payload: payload as PairedPayload | CapturePackagePayload,
    request_headers: normalizeRequestHeaderContext(
      candidate.request_headers,
      payload as { session: { site_id: string; operator_id: string } },
    ),
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

async function saveAppSettings(settings: AppSettings): Promise<void> {
  const { api_key: apiKeyValue, ...plainSettings } = settings;
  await AsyncStorage.setItem(
    APP_SETTINGS_KEY,
    JSON.stringify({ ...plainSettings, api_key: "" }),
  );
  try {
    await SecureStore.setItemAsync(APP_SETTINGS_API_KEY_SECURE_KEY, apiKeyValue);
  } catch {
    await AsyncStorage.setItem(APP_SETTINGS_KEY, JSON.stringify(settings));
  }
}

function extractCreatedRecordId(responseBody: string): number | null {
  try {
    const parsed = JSON.parse(responseBody) as { id?: unknown };
    return typeof parsed.id === "number" ? parsed.id : null;
  } catch {
    return null;
  }
}

function runtimeCaptureMatchesSession(
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

export default function App() {
  const defaultPlatform = Platform.OS === "ios" ? "ios" : "android";
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();

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
  const [platform, setPlatform] = useState<string>(defaultPlatform);
  const [deviceModel, setDeviceModel] = useState<string>(Platform.OS);
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
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [coverageError, setCoverageError] = useState("");
  const [coverageSummary, setCoverageSummary] = useState<CaptureCoverageSummaryResponse | null>(
    null,
  );
  const [settingsHydrated, setSettingsHydrated] = useState(false);
  const [captureRunning, setCaptureRunning] = useState(false);
  const [captureSampleCount, setCaptureSampleCount] = useState(0);
  const [captureAvgMotionNorm, setCaptureAvgMotionNorm] = useState(0);
  const [captureStatus, setCaptureStatus] = useState("Idle");
  const [captureRoiValidRatio, setCaptureRoiValidRatio] = useState(0);
  const [captureLowConfidenceRatio, setCaptureLowConfidenceRatio] = useState(0);
  const [runtimeFlowSeries, setRuntimeFlowSeries] = useState<RuntimeFlowPoint[]>([]);
  const [cameraPreviewReady, setCameraPreviewReady] = useState(false);
  const [roiLocked, setRoiLocked] = useState(false);
  const [roiMotionProxy, setRoiMotionProxy] = useState(0);
  const [roiTextureProxy, setRoiTextureProxy] = useState(0);
  const [roiFrameValid, setRoiFrameValid] = useState(false);
  const [roiFrameCount, setRoiFrameCount] = useState(0);
  const [manualAppMetricsOverride, setManualAppMetricsOverride] = useState(false);
  const [runtimeCaptureContractPayload, setRuntimeCaptureContractPayload] = useState<
    Record<string, unknown> | null
  >(null);
  const syncInFlightRef = useRef(false);
  const autoSyncIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const captureRuntimeRef = useRef<RuntimeCaptureSession | null>(null);
  const cameraPreviewRef = useRef<CameraView | null>(null);
  const roiFrameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const roiFrameInFlightRef = useRef(false);
  const roiFrameStateRef = useRef<RoiFrameAnalysisState>({ prevHash: null, prevLength: null });

  function resetRoiFrameTracking(): void {
    roiFrameStateRef.current = { prevHash: null, prevLength: null };
    setRoiMotionProxy(0);
    setRoiTextureProxy(0);
    setRoiFrameValid(false);
    setRoiFrameCount(0);
  }

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

  const runtimeCurvePreview = useMemo<RuntimeFlowPoint[]>(() => {
    if (runtimeFlowSeries.length <= 32) {
      return runtimeFlowSeries;
    }
    const step = Math.ceil(runtimeFlowSeries.length / 32);
    const selected: RuntimeFlowPoint[] = [];
    for (let index = 0; index < runtimeFlowSeries.length; index += step) {
      selected.push(runtimeFlowSeries[index]);
    }
    const lastPoint = runtimeFlowSeries[runtimeFlowSeries.length - 1];
    if (selected[selected.length - 1] !== lastPoint) {
      selected.push(lastPoint);
    }
    return selected;
  }, [runtimeFlowSeries]);

  const runtimeCurveMaxFlow = useMemo(() => {
    if (runtimeCurvePreview.length === 0) {
      return 1;
    }
    return Math.max(
      1,
      ...runtimeCurvePreview.map((point) => (Number.isFinite(point.flow_ml_s) ? point.flow_ml_s : 0)),
    );
  }, [runtimeCurvePreview]);

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

  useEffect(() => {
    if (captureRuntimeRef.current == null) {
      captureRuntimeRef.current = new RuntimeCaptureSession();
    }
    return () => {
      const runtime = captureRuntimeRef.current;
      if (runtime) {
        void runtime.stop();
      }
      if (roiFrameIntervalRef.current != null) {
        clearInterval(roiFrameIntervalRef.current);
        roiFrameIntervalRef.current = null;
      }
      roiFrameInFlightRef.current = false;
    };
  }, []);

  useEffect(() => {
    const runtime = captureRuntimeRef.current;
    if (!runtime) {
      return;
    }
    runtime.setCameraSignal({
      previewReady: cameraPreviewReady,
      roiLocked,
      roiMotionProxy,
      roiTextureProxy,
      roiValidByFrame: roiFrameValid,
    });
  }, [cameraPreviewReady, roiFrameValid, roiLocked, roiMotionProxy, roiTextureProxy]);

  useEffect(() => {
    if (!cameraPermission?.granted) {
      setCameraPreviewReady(false);
      setRoiLocked(false);
      resetRoiFrameTracking();
    }
  }, [cameraPermission?.granted]);

  useEffect(() => {
    if (!captureRunning || !cameraPermission?.granted || !cameraPreviewReady) {
      if (roiFrameIntervalRef.current != null) {
        clearInterval(roiFrameIntervalRef.current);
        roiFrameIntervalRef.current = null;
      }
      roiFrameInFlightRef.current = false;
      return;
    }

    const runRoiFrameAnalysis = async (): Promise<void> => {
      const camera = cameraPreviewRef.current;
      if (!camera || roiFrameInFlightRef.current) {
        return;
      }
      roiFrameInFlightRef.current = true;
      try {
        const photo = await camera.takePictureAsync({
          base64: true,
          quality: 0.08,
          skipProcessing: true,
        });
        const frameBase64 = photo?.base64;
        if (!frameBase64) {
          return;
        }
        const signal = estimateRoiSignalFromBase64({
          frameBase64,
          prevHash: roiFrameStateRef.current.prevHash,
          prevLength: roiFrameStateRef.current.prevLength,
        });
        roiFrameStateRef.current = {
          prevHash: signal.frameHash,
          prevLength: signal.frameLength,
        };
        setRoiMotionProxy(signal.motionProxy);
        setRoiTextureProxy(signal.textureProxy);
        setRoiFrameValid(signal.roiValid);
        setRoiFrameCount((count) => count + 1);
      } catch {
        // If frame capture fails intermittently, keep session running.
      } finally {
        roiFrameInFlightRef.current = false;
      }
    };

    void runRoiFrameAnalysis();
    roiFrameIntervalRef.current = setInterval(() => {
      void runRoiFrameAnalysis();
    }, 900);

    return () => {
      if (roiFrameIntervalRef.current != null) {
        clearInterval(roiFrameIntervalRef.current);
        roiFrameIntervalRef.current = null;
      }
      roiFrameInFlightRef.current = false;
    };
  }, [cameraPermission?.granted, cameraPreviewReady, captureRunning]);

  async function startRuntimeCapture(): Promise<void> {
    const runtime = captureRuntimeRef.current ?? new RuntimeCaptureSession();
    captureRuntimeRef.current = runtime;

    try {
      if (!cameraPermission?.granted) {
        const permissionResult = await requestCameraPermission();
        if (!permissionResult.granted) {
          Alert.alert(
            "Camera permission missing",
            "Camera permission is required for ROI validity checks.",
          );
        }
      }
      if (!roiLocked) {
        Alert.alert(
          "ROI not locked",
          "Lock ROI before capture for better quality. Capture will continue but may be marked repeat/reject.",
        );
      }
      resetRoiFrameTracking();
      setCaptureStatus("Requesting permissions...");
      const startResult = await runtime.start();
      setCaptureRunning(true);
      setCaptureSampleCount(0);
      setCaptureAvgMotionNorm(0);
      setCaptureRoiValidRatio(0);
      setCaptureLowConfidenceRatio(0);
      setRuntimeFlowSeries([]);
      setRuntimeCaptureContractPayload(null);
      setMeasuredAt(startResult.startedAtIso);
      setCaptureStatus(
        `Capture running. mic=${startResult.permissions.microphoneGranted ? "ok" : "no"}, ` +
          `camera=${startResult.permissions.cameraGranted ? "ok" : "no"}, ` +
          `motion=${startResult.permissions.motionGranted ? "ok" : "no"}`,
      );
      if (!startResult.permissions.cameraGranted) {
        Alert.alert(
          "Camera permission missing",
          "Capture will continue with audio+motion only; ROI quality flags may degrade.",
        );
      }
    } catch (error) {
      setCaptureRunning(false);
      setCaptureStatus(`Capture start failed: ${String(error)}`);
      Alert.alert("Capture start failed", String(error));
    }
  }

  async function stopRuntimeCapture(): Promise<void> {
    const runtime = captureRuntimeRef.current;
    if (!runtime) {
      return;
    }

    try {
      const stopResult = await runtime.stop();
      setCaptureRunning(false);
      setCaptureSampleCount(stopResult.sampleCount);
      setCaptureAvgMotionNorm(stopResult.averageMotionNorm);
      setCaptureRoiValidRatio(stopResult.quality.roiValidRatio);
      setCaptureLowConfidenceRatio(stopResult.quality.lowConfidenceRatio);
      setRuntimeFlowSeries(stopResult.flowSeries);
      setDeviceModel(stopResult.deviceModel);
      if (!manualAppMetricsOverride) {
        setAppQmax(stopResult.derived.qmaxMlS.toFixed(3));
        setAppQavg(stopResult.derived.qavgMlS.toFixed(3));
        setAppVvoid(stopResult.derived.vvoidMl.toFixed(3));
        setAppFlowTime(stopResult.derived.flowTimeS.toFixed(3));
        setAppTqmax(stopResult.derived.tqmaxS.toFixed(3));
      }
      setAppQualityScore(stopResult.quality.qualityScore.toFixed(1));
      setAppQualityStatus(stopResult.quality.qualityStatus);

      const contractPayload = buildCaptureContractPayloadFromSamples({
        sessionId: sessionId.trim(),
        syncId: syncId.trim() || null,
        startedAtIso: stopResult.startedAtIso,
        captureMode,
        deviceModel: stopResult.deviceModel,
        iosVersion: stopResult.osVersion,
        appVersion: appVersion.trim() || null,
        samples: stopResult.samples,
        minDepthConfidence: 0.6,
        sourceLabel: "runtime-audio-imu",
        analysis: {
          runtime_flow_series: stopResult.flowSeries,
          runtime_quality: {
            quality_score: stopResult.quality.qualityScore,
            quality_status: stopResult.quality.qualityStatus,
            roi_valid_ratio: stopResult.quality.roiValidRatio,
            low_confidence_ratio: stopResult.quality.lowConfidenceRatio,
          },
        },
      });
      setRuntimeCaptureContractPayload(contractPayload as unknown as Record<string, unknown>);
      setCaptureStatus(
        `Capture stopped. samples=${stopResult.sampleCount}, quality=${stopResult.quality.qualityStatus}, score=${stopResult.quality.qualityScore.toFixed(1)}`,
      );
      if (stopResult.derived.eventStartTs != null && stopResult.derived.eventEndTs != null) {
        const runtimeNote =
          `runtime_event_start_s=${stopResult.derived.eventStartTs.toFixed(3)}, ` +
          `runtime_event_end_s=${stopResult.derived.eventEndTs.toFixed(3)}`;
        setNotes((existing) => (existing.trim() ? `${existing}; ${runtimeNote}` : runtimeNote));
      }
    } catch (error) {
      setCaptureRunning(false);
      setCaptureStatus(`Capture stop failed: ${String(error)}`);
      Alert.alert("Capture stop failed", String(error));
    }
  }

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

  function endpointPath(endpoint: PendingEndpoint): string {
    if (endpoint === "capture_packages") {
      return "/api/v1/capture-packages";
    }
    return "/api/v1/paired-measurements";
  }

  function buildCapturePackagePayloadFromPaired(
    currentPayload: PairedPayload,
    pairedMeasurementId: number | null,
  ): CapturePackagePayload {
    let captureContractPayload: Record<string, unknown>;
    let notes = "mobile_scaffold_capture_contract_v0.1";
    const runtimePayload = runtimeCaptureContractPayload;
    if (runtimePayload && runtimeCaptureMatchesSession(runtimePayload, currentPayload.session)) {
      captureContractPayload = runtimePayload;
      notes = "mobile_runtime_capture_contract_audio_imu_v0.1";
    } else {
      captureContractPayload = buildCaptureContractPayload({
        sessionId: currentPayload.session.session_id,
        syncId: currentPayload.session.sync_id,
        startedAtIso: currentPayload.session.measured_at,
        captureMode: currentPayload.session.capture_mode,
        deviceModel: currentPayload.session.device_model,
        iosVersion: String(Platform.Version),
        appVersion: currentPayload.session.app_version,
        qmaxMlS: currentPayload.app.metrics.qmax_ml_s,
        qavgMlS: currentPayload.app.metrics.qavg_ml_s,
        flowTimeS: currentPayload.app.metrics.flow_time_s,
      }) as unknown as Record<string, unknown>;
    }
    return {
      session: currentPayload.session,
      package_type: "capture_contract_json",
      capture_payload: captureContractPayload,
      paired_measurement_id: pairedMeasurementId,
      notes,
    };
  }

  async function attemptSubmitEndpoint(
    endpoint: PendingEndpoint,
    endpointPayload: PairedPayload | CapturePackagePayload,
    headerContext?: RequestHeaderContext,
  ): Promise<SubmitAttemptResult> {
    const url = `${apiBaseUrl.replace(/\/$/, "")}${endpointPath(endpoint)}`;
    try {
      const response = await fetchWithTimeout(url, {
        method: "POST",
        headers: buildRequestHeaders(true, headerContext),
        body: JSON.stringify(endpointPayload),
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

  async function enqueuePendingJob(
    endpoint: PendingEndpoint,
    endpointPayload: PairedPayload | CapturePackagePayload,
    headerContext: RequestHeaderContext,
    lastError: string | null,
    lastStatusCode: number | null,
  ): Promise<void> {
    const pendingItem: PendingSubmission = {
      id: createPendingId(),
      created_at: new Date().toISOString(),
      endpoint,
      payload: endpointPayload,
      request_headers: headerContext,
      attempt_count: 0,
      last_attempt_at: null,
      last_error: lastError,
      last_status_code: lastStatusCode,
    };
    await enqueuePendingSubmission(pendingItem);
  }

  async function syncPendingSubmissions(showAlert = true): Promise<void> {
    if (syncInFlightRef.current) {
      return;
    }
    syncInFlightRef.current = true;
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
      let syncedPaired = 0;
      let syncedCapture = 0;
      let droppedNonRetryable = 0;

      for (const item of queue) {
        const headerContext = resolvePendingHeaderContext(item);
        const result = await attemptSubmitEndpoint(item.endpoint, item.payload, headerContext);
        const attemptedItem: PendingSubmission = {
          ...item,
          request_headers: headerContext,
          attempt_count: item.attempt_count + 1,
          last_attempt_at: new Date().toISOString(),
          last_status_code: result.statusCode,
          last_error: result.ok ? null : result.body,
        };
        if (result.ok) {
          if (item.endpoint === "capture_packages") {
            syncedCapture += 1;
          } else {
            syncedPaired += 1;
          }
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
        `Sync completed. Synced paired: ${syncedPaired}, synced capture: ${syncedCapture}, ` +
        `remaining retryable: ${remaining.length}, ` +
        `dropped non-retryable: ${droppedNonRetryable}.`;
      setSyncStatusMessage(statusMessage);
      setLastResponse(statusMessage);
      if (showAlert) {
        Alert.alert("Sync completed", statusMessage);
      }
    } finally {
      syncInFlightRef.current = false;
      setSyncingPending(false);
    }
  }

  useEffect(() => {
    if (!settingsHydrated || pendingQueue.length === 0) {
      if (autoSyncIntervalRef.current != null) {
        clearInterval(autoSyncIntervalRef.current);
        autoSyncIntervalRef.current = null;
      }
      return;
    }

    if (autoSyncIntervalRef.current == null) {
      autoSyncIntervalRef.current = setInterval(() => {
        void syncPendingSubmissions(false);
      }, 25000);
    }

    void syncPendingSubmissions(false);

    return () => {
      if (autoSyncIntervalRef.current != null) {
        clearInterval(autoSyncIntervalRef.current);
        autoSyncIntervalRef.current = null;
      }
    };
  }, [
    actorRole,
    apiBaseUrl,
    apiKey,
    operatorId,
    pendingQueue.length,
    requestTimeoutMs,
    settingsHydrated,
    siteId,
  ]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active" && pendingQueue.length > 0) {
        void syncPendingSubmissions(false);
      }
    });
    return () => {
      subscription.remove();
    };
  }, [
    actorRole,
    apiBaseUrl,
    apiKey,
    operatorId,
    pendingQueue.length,
    requestTimeoutMs,
    siteId,
  ]);

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
    if (captureRunning) {
      return "Stop runtime capture before submitting.";
    }
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
      const result = await attemptSubmitEndpoint(
        "paired_measurements",
        payload,
        requestHeaderContext,
      );
      if (result.ok) {
        const pairedMeasurementId = extractCreatedRecordId(result.body);
        const capturePayload = buildCapturePackagePayloadFromPaired(
          payload,
          pairedMeasurementId,
        );
        const captureResult = await attemptSubmitEndpoint(
          "capture_packages",
          capturePayload,
          requestHeaderContext,
        );
        if (!captureResult.ok) {
          if (captureResult.retryable) {
            await enqueuePendingJob(
              "capture_packages",
              capturePayload,
              requestHeaderContext,
              captureResult.body,
              captureResult.statusCode,
            );
            const queuedMessage =
              `Paired uploaded; capture package queued for retry: ` +
              `${captureResult.statusCode ? `HTTP ${captureResult.statusCode}` : "NETWORK"} ` +
              `${captureResult.body}`;
            setLastResponse(queuedMessage);
            Alert.alert("Submitted with queued capture", queuedMessage);
          } else {
            const warningMessage =
              `Paired measurement uploaded, but capture package rejected: ` +
              `${captureResult.statusCode ? `HTTP ${captureResult.statusCode}` : "ERROR"} ` +
              `${captureResult.body}`;
            setLastResponse(warningMessage);
            Alert.alert("Submitted with warning", warningMessage);
          }
        } else {
          setLastResponse("Paired measurement and capture package uploaded.");
          Alert.alert("Submitted", "Paired measurement and capture package uploaded.");
        }
        setRuntimeCaptureContractPayload(null);
        setCaptureSampleCount(0);
        setCaptureAvgMotionNorm(0);
        setCaptureRoiValidRatio(0);
        setCaptureLowConfidenceRatio(0);
        setRuntimeFlowSeries([]);
        setCaptureStatus("Idle");
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

      const capturePayloadWithoutPair = buildCapturePackagePayloadFromPaired(payload, null);
      await enqueuePendingJob(
        "paired_measurements",
        payload,
        requestHeaderContext,
        result.body,
        result.statusCode,
      );
      await enqueuePendingJob(
        "capture_packages",
        capturePayloadWithoutPair,
        requestHeaderContext,
        "queued_with_paired_retry",
        null,
      );
      setLastResponse(
        `Queued paired+capture for retry. Last paired error: ${
          result.statusCode ? `HTTP ${result.statusCode}` : "NETWORK"
        } ${result.body}`
      );
      Alert.alert(
        "Saved offline",
        "No successful upload now. Paired and capture records added to pending queue.",
      );
      setRuntimeCaptureContractPayload(null);
      setCaptureSampleCount(0);
      setCaptureAvgMotionNorm(0);
      setCaptureRoiValidRatio(0);
      setCaptureLowConfidenceRatio(0);
      setRuntimeFlowSeries([]);
      setCaptureStatus("Idle");
      setSessionId(createSessionId());
      setSyncId(createSyncId());
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

  async function loadCaptureCoverageSummary() {
    const baseUrl = apiBaseUrl.replace(/\/$/, "");
    const params = new URLSearchParams();
    if (siteId.trim()) {
      params.set("site_id", siteId.trim());
    }
    if (summarySyncId.trim()) {
      params.set("sync_id", summarySyncId.trim());
    }
    params.set("quality_status", summaryQualityStatus);
    const url = `${baseUrl}/api/v1/capture-coverage-summary?${params.toString()}`;

    setCoverageLoading(true);
    setCoverageError("");

    try {
      const response = await fetchWithTimeout(url, {
        method: "GET",
        headers: buildRequestHeaders(false),
      });
      const body = await response.text();
      if (!response.ok) {
        setCoverageSummary(null);
        setCoverageError(`HTTP ${response.status}: ${body}`);
        return;
      }
      setCoverageSummary(JSON.parse(body) as CaptureCoverageSummaryResponse);
    } catch (error) {
      setCoverageSummary(null);
      setCoverageError(String(error));
    } finally {
      setCoverageLoading(false);
    }
  }

  async function loadBothSummaries() {
    await Promise.all([loadComparisonSummary(), loadCaptureCoverageSummary()]);
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Uroflow Field Capture</Text>
        <Text style={styles.subtitle}>Pair app result with reference uroflowmeter</Text>
        <Text style={styles.helperText}>
          Capture contract auto-upload enabled: runtime audio/IMU samples are preferred, scaffold is
          fallback.
        </Text>

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
            {item.id}: endpoint={item.endpoint}, attempts={item.attempt_count}
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

        <Text style={styles.sectionTitle}>Runtime Capture (Audio + IMU + Camera Permission)</Text>
        <Text style={styles.captureStatusText}>{captureStatus}</Text>
        <Text style={styles.captureStatusText}>
          Camera permission: {cameraPermission?.granted ? "granted" : "not granted"}, preview:{" "}
          {cameraPreviewReady ? "ready" : "not ready"}, ROI lock: {roiLocked ? "on" : "off"}
        </Text>
        <Text style={styles.captureStatusText}>
          Samples: {captureSampleCount}, avg motion norm: {captureAvgMotionNorm.toFixed(3)}
        </Text>
        <Text style={styles.captureStatusText}>
          quality flags: roi_valid_ratio={captureRoiValidRatio.toFixed(3)}, low_confidence_ratio=
          {captureLowConfidenceRatio.toFixed(3)}
        </Text>
        <Text style={styles.captureStatusText}>
          Contract payload: {runtimeCaptureContractPayload ? "ready" : "not ready (scaffold fallback)"}
        </Text>
        {!cameraPermission?.granted ? (
          <Pressable style={styles.summaryButton} onPress={() => void requestCameraPermission()}>
            <Text style={styles.submitButtonText}>Grant Camera Permission</Text>
          </Pressable>
        ) : (
          <View style={styles.cameraPreviewWrap}>
            <CameraView
              ref={cameraPreviewRef}
              style={styles.cameraPreview}
              facing="back"
              onCameraReady={() => setCameraPreviewReady(true)}
              onMountError={() => {
                setCameraPreviewReady(false);
                setCaptureStatus("Camera preview mount error; ROI validity may fail.");
              }}
            />
          </View>
        )}
        <Pressable
          style={[styles.summaryButton, !cameraPermission?.granted && styles.submitButtonDisabled]}
          onPress={() => setRoiLocked((current) => !current)}
          disabled={!cameraPermission?.granted}
        >
          <Text style={styles.submitButtonText}>{roiLocked ? "Unlock ROI" : "Lock ROI"}</Text>
        </Pressable>
        <Text style={styles.captureStatusText}>
          ROI frames: {roiFrameCount}, valid: {roiFrameValid ? "yes" : "no"}, motion proxy:{" "}
          {roiMotionProxy.toFixed(3)}, texture proxy: {roiTextureProxy.toFixed(3)}
        </Text>
        <Pressable
          style={styles.summaryButton}
          onPress={() => setManualAppMetricsOverride((current) => !current)}
        >
          <Text style={styles.submitButtonText}>
            App metrics mode: {manualAppMetricsOverride ? "manual" : "runtime auto-fill"}
          </Text>
        </Pressable>
        <View style={styles.buttonRow}>
          <Pressable
            style={[
              styles.summaryButton,
              styles.buttonGrow,
              captureRunning && styles.submitButtonDisabled,
            ]}
            onPress={() => void startRuntimeCapture()}
            disabled={captureRunning}
          >
            <Text style={styles.submitButtonText}>
              {captureRunning ? "Capture running..." : "Start Capture"}
            </Text>
          </Pressable>
          <Pressable
            style={[
              styles.dangerButton,
              styles.buttonGrow,
              !captureRunning && styles.submitButtonDisabled,
            ]}
            onPress={() => void stopRuntimeCapture()}
            disabled={!captureRunning}
          >
            <Text style={styles.submitButtonText}>Stop Capture</Text>
          </Pressable>
        </View>

        <Text style={styles.sectionTitle}>Runtime Q(t) Preview</Text>
        <View style={styles.curveBox}>
          {runtimeCurvePreview.length === 0 ? (
            <Text style={styles.responseText}>No runtime curve yet. Run capture and press Stop.</Text>
          ) : (
            runtimeCurvePreview.map((point, index) => {
              const widthPct = Math.min(100, Math.max(0, (point.flow_ml_s / runtimeCurveMaxFlow) * 100));
              return (
                <View key={`${point.t_s.toFixed(3)}-${index}`} style={styles.curveRow}>
                  <Text style={styles.curveTimeText}>{point.t_s.toFixed(1)}s</Text>
                  <View style={styles.curveBarTrack}>
                    <View style={[styles.curveBarFill, { width: `${widthPct}%` }]} />
                  </View>
                  <Text style={styles.curveValueText}>{point.flow_ml_s.toFixed(1)}</Text>
                </View>
              );
            })
          )}
        </View>

        <Text style={styles.sectionTitle}>Session</Text>
        <LabeledInput label="Session ID" value={sessionId} onChangeText={setSessionId} />
        <LabeledInput label="Sync ID" value={syncId} onChangeText={setSyncId} />
        <LabeledInput label="Site ID" value={siteId} onChangeText={setSiteId} />
        <LabeledInput label="Subject ID" value={subjectId} onChangeText={setSubjectId} />
        <LabeledInput label="Operator ID" value={operatorId} onChangeText={setOperatorId} />
        <LabeledInput label="Attempt Number" value={attemptNumber} onChangeText={setAttemptNumber} keyboardType="number-pad" />
        <LabeledInput label="Measured At (ISO)" value={measuredAt} onChangeText={setMeasuredAt} />
        <LabeledInput
          label="Platform (ios/android)"
          value={platform}
          onChangeText={setPlatform}
        />
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
        <Text style={styles.helperText}>
          Uses current filters: site_id + optional sync_id + quality status.
        </Text>
        <Pressable
          style={[
            styles.summaryButton,
            (summaryLoading || coverageLoading) && styles.submitButtonDisabled,
          ]}
          onPress={() => void loadBothSummaries()}
          disabled={summaryLoading || coverageLoading}
        >
          <Text style={styles.submitButtonText}>
            {summaryLoading || coverageLoading
              ? "Loading both summaries..."
              : "Load Both Summaries"}
          </Text>
        </Pressable>
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

        <Text style={styles.sectionTitle}>Capture Coverage Summary</Text>
        <Pressable
          style={[styles.summaryButton, coverageLoading && styles.submitButtonDisabled]}
          onPress={loadCaptureCoverageSummary}
          disabled={coverageLoading}
        >
          <Text style={styles.submitButtonText}>
            {coverageLoading ? "Loading..." : "Load Coverage Summary"}
          </Text>
        </Pressable>
        {coverageError ? <Text style={styles.summaryErrorText}>{coverageError}</Text> : null}
        <View style={styles.responseBox}>
          {coverageSummary ? (
            <>
              <Text style={styles.summaryText}>
                Paired total: {coverageSummary.paired_total}, with capture:{" "}
                {coverageSummary.paired_with_capture}, without capture:{" "}
                {coverageSummary.paired_without_capture}
              </Text>
              <Text style={styles.summaryText}>
                Coverage ratio:{" "}
                <Text
                  style={
                    coverageSummary.coverage_ratio >= COVERAGE_GOAL_RATIO
                      ? styles.coverageGoodText
                      : styles.coverageBadText
                  }
                >
                  {(coverageSummary.coverage_ratio * 100).toFixed(1)}%
                </Text>{" "}
                (target: {(COVERAGE_GOAL_RATIO * 100).toFixed(0)}%)
              </Text>
              <Text style={styles.summaryText}>
                Match modes: paired_id=
                {coverageSummary.capture_match_distribution.paired_id ?? 0}, session_identity=
                {coverageSummary.capture_match_distribution.session_identity ?? 0}, none=
                {coverageSummary.capture_match_distribution.none ?? 0}
              </Text>
              <Text style={styles.summaryText}>
                Quality: valid={coverageSummary.quality_distribution.valid ?? 0}, repeat=
                {coverageSummary.quality_distribution.repeat ?? 0}, reject=
                {coverageSummary.quality_distribution.reject ?? 0}
              </Text>
            </>
          ) : (
            <Text style={styles.responseText}>No coverage summary loaded yet</Text>
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
  helperText: {
    marginBottom: 10,
    fontSize: 12,
    color: "#334155",
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
  captureStatusText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 4,
  },
  cameraPreviewWrap: {
    marginTop: 8,
    marginBottom: 8,
    borderRadius: 10,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#0f172a",
  },
  cameraPreview: {
    width: "100%",
    height: 180,
  },
  curveBox: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: "#d1d5db",
    backgroundColor: "#ffffff",
    borderRadius: 8,
    padding: 10,
  },
  curveRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
  },
  curveTimeText: {
    width: 42,
    color: "#334155",
    fontSize: 11,
  },
  curveBarTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#e2e8f0",
    overflow: "hidden",
    marginHorizontal: 8,
  },
  curveBarFill: {
    height: 8,
    borderRadius: 4,
    backgroundColor: "#0f766e",
  },
  curveValueText: {
    width: 44,
    textAlign: "right",
    color: "#0f172a",
    fontSize: 11,
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
  coverageGoodText: {
    color: "#166534",
    fontWeight: "700",
  },
  coverageBadText: {
    color: "#b91c1c",
    fontWeight: "700",
  },
});
