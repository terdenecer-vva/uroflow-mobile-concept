import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  Text,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { CameraView, useCameraPermissions } from "expo-camera";
import {
  attemptSubmitEndpoint,
  buildBaseUrl,
  buildRequestHeaders,
  fetchWithTimeout,
} from "./src/api/clinicalHub";
import {
  buildCaptureContractPayload,
  buildCaptureContractPayloadFromSamples,
} from "./src/capture/buildCaptureContract";
import {
  RuntimeCaptureSession,
  type RuntimeFlowPoint,
} from "./src/capture/runtimeCaptureSession";
import { estimateRoiSignalFromBase64 } from "./src/capture/roiSignalEstimator";
import { ApiConnectionSection } from "./src/components/ApiConnectionSection";
import { LabeledInput } from "./src/components/LabeledInput";
import { RuntimeCaptureSection } from "./src/components/RuntimeCaptureSection";
import { styles } from "./src/styles/appStyles";
import { usePendingSyncQueue } from "./src/hooks/usePendingSyncQueue";
import {
  loadAppSettings,
  saveAppSettings,
} from "./src/storage/appStorage";
import type {
  AppSettings,
  AuthContextResponse,
  CaptureCoverageSummaryResponse,
  CapturePackagePayload,
  ComparisonSummaryResponse,
  PairedPayload,
  QualityStatus,
  RequestHeaderContext,
  RoiFrameAnalysisState,
  SummaryQualityStatus,
} from "./src/types";
import {
  COVERAGE_GOAL_RATIO,
  DEFAULT_REQUEST_TIMEOUT_MS,
  buildHeaderContextFromValues,
  createSessionId,
  createSyncId,
  extractCreatedRecordId,
  formatNullable,
  parseNumber,
  runtimeCaptureMatchesSession,
} from "./src/utils/appHelpers";

const defaultMeasuredAt = new Date().toISOString().slice(0, 19) + "Z";

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

  const requestHeaderContext = useMemo<RequestHeaderContext>(
    () => buildHeaderContextFromValues(apiKey, actorRole, siteId, operatorId),
    [actorRole, apiKey, operatorId, siteId],
  );

  const {
    pendingQueue,
    syncingPending,
    syncStatusMessage,
    enqueuePendingJob,
    syncPendingSubmissions,
    clearPendingSubmissions,
  } = usePendingSyncQueue({
    apiBaseUrl,
    requestTimeoutMs,
    requestHeaderContext,
    settingsHydrated,
    onLastResponse: setLastResponse,
  });

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
      const settings = await loadAppSettings();
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

  function createCurrentRequestHeaderContext(): RequestHeaderContext {
    return requestHeaderContext;
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

  async function testApiConnection(): Promise<void> {
    const baseUrl = buildBaseUrl(apiBaseUrl);
    const authContextUrl = `${baseUrl}/api/v1/auth-context`;
    try {
      const response = await fetchWithTimeout(
        authContextUrl,
        {
          method: "GET",
          headers: buildRequestHeaders(false, createCurrentRequestHeaderContext()),
        },
        requestTimeoutMs,
      );
      if (response.status === 404) {
        const healthResponse = await fetchWithTimeout(
          `${baseUrl}/health`,
          {
            method: "GET",
            headers: buildRequestHeaders(false, createCurrentRequestHeaderContext()),
          },
          requestTimeoutMs,
        );
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
      const result = await attemptSubmitEndpoint({
        apiBaseUrl,
        requestTimeoutMs,
        endpoint: "paired_measurements",
        endpointPayload: payload,
        headerContext: requestHeaderContext,
      });
      if (result.ok) {
        const pairedMeasurementId = extractCreatedRecordId(result.body);
        const capturePayload = buildCapturePackagePayloadFromPaired(
          payload,
          pairedMeasurementId,
        );
        const captureResult = await attemptSubmitEndpoint({
          apiBaseUrl,
          requestTimeoutMs,
          endpoint: "capture_packages",
          endpointPayload: capturePayload,
          headerContext: requestHeaderContext,
        });
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
    const baseUrl = buildBaseUrl(apiBaseUrl);
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
      const response = await fetchWithTimeout(
        url,
        {
          method: "GET",
          headers: buildRequestHeaders(false, createCurrentRequestHeaderContext()),
        },
        requestTimeoutMs,
      );
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
    const baseUrl = buildBaseUrl(apiBaseUrl);
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
      const response = await fetchWithTimeout(
        url,
        {
          method: "GET",
          headers: buildRequestHeaders(false, createCurrentRequestHeaderContext()),
        },
        requestTimeoutMs,
      );
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

        <ApiConnectionSection
          apiBaseUrl={apiBaseUrl}
          apiKey={apiKey}
          actorRole={actorRole}
          requestTimeoutMs={requestTimeoutMs}
          pendingQueue={pendingQueue}
          syncingPending={syncingPending}
          syncStatusMessage={syncStatusMessage}
          onApiBaseUrlChange={setApiBaseUrl}
          onApiKeyChange={setApiKey}
          onActorRoleChange={setActorRole}
          onRequestTimeoutMsChange={setRequestTimeoutMs}
          onTestApiConnection={testApiConnection}
          onSyncPendingSubmissions={syncPendingSubmissions}
          onClearPendingSubmissions={clearPendingSubmissions}
        />

        <RuntimeCaptureSection
          cameraPermissionGranted={cameraPermission?.granted ?? false}
          cameraPreviewReady={cameraPreviewReady}
          cameraPreviewRef={cameraPreviewRef}
          captureAvgMotionNorm={captureAvgMotionNorm}
          captureLowConfidenceRatio={captureLowConfidenceRatio}
          captureRoiValidRatio={captureRoiValidRatio}
          captureRunning={captureRunning}
          captureSampleCount={captureSampleCount}
          captureStatus={captureStatus}
          flowSeries={runtimeFlowSeries}
          manualAppMetricsOverride={manualAppMetricsOverride}
          roiFrameCount={roiFrameCount}
          roiFrameValid={roiFrameValid}
          roiLocked={roiLocked}
          roiMotionProxy={roiMotionProxy}
          roiTextureProxy={roiTextureProxy}
          runtimeCaptureContractReady={runtimeCaptureContractPayload !== null}
          onCameraMountError={() => {
            setCameraPreviewReady(false);
            setCaptureStatus("Camera preview mount error; ROI validity may fail.");
          }}
          onCameraReady={() => setCameraPreviewReady(true)}
          onRequestCameraPermission={requestCameraPermission}
          onStartRuntimeCapture={startRuntimeCapture}
          onStopRuntimeCapture={stopRuntimeCapture}
          onToggleManualAppMetricsOverride={() =>
            setManualAppMetricsOverride((current) => !current)
          }
          onToggleRoiLock={() => setRoiLocked((current) => !current)}
        />

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
