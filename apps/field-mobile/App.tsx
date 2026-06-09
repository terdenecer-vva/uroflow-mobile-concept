import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Platform,
  SafeAreaView,
  ScrollView,
  Text,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as Device from "expo-device";
import {
  attemptSubmitEndpoint,
  buildRequestHeaders,
  fetchWithTimeout,
} from "./src/api/clinicalHub";
import {
  buildClinicalHubPreflight,
  isClinicalHubPreflightActionAllowed,
} from "./src/api/clinicalHubPreflight";
import {
  buildApiCheckFailedMessage,
  buildAuthContextCheckFailedMessage,
  buildAuthContextOkMessage,
  buildAuthContextUrl,
  buildHealthCheckFailedMessage,
  buildHealthUrl,
} from "./src/api/connectionCheck";
import {
  buildCaptureCoverageSummaryUrl,
  buildComparisonSummaryUrl,
} from "./src/api/summaryRequests";
import { buildCaptureContractPayloadFromSamples } from "./src/capture/buildCaptureContract";
import {
  RuntimeCaptureSession,
  type RuntimeFlowPoint,
} from "./src/capture/runtimeCaptureSession";
import { buildRuntimeCaptureReadiness } from "./src/capture/runtimeMetrics";
import { APP_MODEL_ID, APP_RELEASE_VERSION } from "./src/config/releaseMetadata";
import { estimateRoiSignalFromBase64 } from "./src/capture/roiSignalEstimator";
import { APP_DEFAULT_CAPTURE_MODE } from "./src/config/appConfig";
import {
  buildRuntimeReleaseGuard,
  isRuntimeReleaseGuardActionAllowed,
} from "./src/config/runtimeReleaseGuard";
import { ApiConnectionSection } from "./src/components/ApiConnectionSection";
import { MeasurementFormSection } from "./src/components/MeasurementFormSection";
import { ResponseAndSummarySection } from "./src/components/ResponseAndSummarySection";
import { RuntimeCaptureSection } from "./src/components/RuntimeCaptureSection";
import { ReleaseIdentitySection } from "./src/components/ReleaseIdentitySection";
import { ClinicalClaimsNotice } from "./src/components/ClinicalClaimsNotice";
import { styles } from "./src/styles/appStyles";
import { usePendingSyncQueue } from "./src/hooks/usePendingSyncQueue";
import { buildCapturePackagePayloadFromPaired } from "./src/payload/capturePackagePayload";
import {
  buildPairedPayloadFromForm,
  validatePairedPayloadForSubmission,
} from "./src/payload/pairedPayload";
import {
  loadAppSettings,
  saveAppSettings,
} from "./src/storage/appStorage";
import { DEFAULT_API_BASE_URL } from "./src/storage/appSettingsStorage";
import {
  buildNonRetryableUploadMessage,
  buildQueuedCapturePackageMessage,
  buildQueuedPairedAndCaptureMessage,
  buildRejectedCapturePackageMessage,
} from "./src/utils/submitOutcome";
import type {
  AppSettings,
  AuthContextResponse,
  CaptureCoverageSummaryResponse,
  ComparisonSummaryResponse,
  PairedPayload,
  QualityStatus,
  RequestHeaderContext,
  RoiFrameAnalysisState,
  SummaryQualityStatus,
} from "./src/types";
import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  buildHeaderContextFromValues,
  createRequestId,
  createSessionId,
  createSyncId,
  extractCreatedRecordId,
  formatSafeExceptionMessage,
  formatSafeResponseProblem,
} from "./src/utils/appHelpers";
import {
  buildCaptureModeSubmissionError,
  buildCaptureModeSubmissionWarning,
} from "./src/utils/captureModePolicy";
import { buildDeviceModelLabel } from "./src/utils/deviceIdentity";
import { buildLowQualitySubmissionWarning } from "./src/utils/qualityPolicy";

const defaultMeasuredAt = new Date().toISOString().slice(0, 19) + "Z";

export default function App() {
  const defaultPlatform = Platform.OS === "ios" ? "ios" : "android";
  const defaultDeviceModel = buildDeviceModelLabel({
    platform: defaultPlatform,
    modelName: Device.modelName,
    manufacturer: Device.manufacturer,
    brand: Device.brand,
  });
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();

  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
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
  const [deviceModel, setDeviceModel] = useState<string>(defaultDeviceModel);
  const [appVersion, setAppVersion] = useState(APP_RELEASE_VERSION);
  const [captureMode, setCaptureMode] = useState(APP_DEFAULT_CAPTURE_MODE);

  const [appQmax, setAppQmax] = useState("");
  const [appQavg, setAppQavg] = useState("");
  const [appVvoid, setAppVvoid] = useState("");
  const [appFlowTime, setAppFlowTime] = useState("");
  const [appTqmax, setAppTqmax] = useState("");
  const [appQualityStatus, setAppQualityStatus] = useState<QualityStatus>("valid");
  const [appQualityScore, setAppQualityScore] = useState("");
  const [appModelId, setAppModelId] = useState(APP_MODEL_ID);

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
  const [captureHighMotionRatio, setCaptureHighMotionRatio] = useState(0);
  const [captureTimingGapWarning, setCaptureTimingGapWarning] = useState(false);
  const [captureAlignmentDriftWarning, setCaptureAlignmentDriftWarning] = useState(false);
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
  const clinicalHubPreflight = useMemo(
    () => buildClinicalHubPreflight(apiBaseUrl),
    [apiBaseUrl],
  );
  const runtimeReleaseGuard = useMemo(() => buildRuntimeReleaseGuard(), []);
  const qualitySubmissionWarning = useMemo(
    () => buildLowQualitySubmissionWarning(appQualityStatus, runtimeCaptureContractPayload),
    [appQualityStatus, runtimeCaptureContractPayload],
  );
  const captureModeSubmissionWarning = useMemo(
    () => buildCaptureModeSubmissionWarning(captureMode),
    [captureMode],
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
    return buildPairedPayloadFromForm({
      sessionId,
      syncId,
      siteId,
      subjectId,
      operatorId,
      attemptNumber,
      measuredAt,
      platform,
      deviceModel,
      appVersion,
      captureMode,
      appQmax,
      appQavg,
      appVvoid,
      appFlowTime,
      appTqmax,
      appQualityStatus,
      appQualityScore,
      appModelId,
      refQmax,
      refQavg,
      refVvoid,
      refFlowTime,
      refTqmax,
      refDeviceModel,
      refDeviceSerial,
      notes,
    });
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
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      setLastResponse(runtimeReleaseGuard.message);
      Alert.alert("Release guard blocked", runtimeReleaseGuard.message);
    }
  }, [runtimeReleaseGuard]);

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
    if ((!captureRunning && !roiLocked) || !cameraPermission?.granted || !cameraPreviewReady) {
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
  }, [cameraPermission?.granted, cameraPreviewReady, captureRunning, roiLocked]);

  function toggleRoiLock(): void {
    resetRoiFrameTracking();
    setRoiLocked((current) => !current);
  }

  async function startRuntimeCapture(): Promise<void> {
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      setCaptureStatus(runtimeReleaseGuard.message);
      Alert.alert("Release guard blocked", runtimeReleaseGuard.message);
      return;
    }
    const captureModeError = buildCaptureModeSubmissionError(captureMode);
    if (captureModeError) {
      setCaptureStatus(`Capture mode blocked: ${captureModeError}`);
      Alert.alert("Capture mode blocked", captureModeError);
      return;
    }

    const runtime = captureRuntimeRef.current ?? new RuntimeCaptureSession();
    captureRuntimeRef.current = runtime;

    try {
      let cameraPermissionGranted = cameraPermission?.granted ?? false;
      if (!cameraPermission?.granted) {
        const permissionResult = await requestCameraPermission();
        cameraPermissionGranted = permissionResult.granted;
        if (!cameraPermissionGranted) {
          Alert.alert(
            "Camera permission missing",
            "Camera permission is required for ROI validity checks.",
          );
        }
      }

      const captureReadiness = buildRuntimeCaptureReadiness({
        cameraPermissionGranted,
        cameraPreviewReady,
        roiLocked,
        roiFrameCount,
        roiFrameValid,
      });
      if (!captureReadiness.ready) {
        setCaptureStatus(`Capture preflight blocked: ${captureReadiness.message}`);
        Alert.alert("Capture preflight blocked", captureReadiness.message);
        return;
      }

      setCaptureStatus("Requesting permissions...");
      const startResult = await runtime.start();
      setCaptureRunning(true);
      setCaptureSampleCount(0);
      setCaptureAvgMotionNorm(0);
      setCaptureRoiValidRatio(0);
      setCaptureLowConfidenceRatio(0);
      setCaptureHighMotionRatio(0);
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
      const message = formatSafeExceptionMessage(error);
      setCaptureStatus(`Capture start failed: ${message}`);
      Alert.alert("Capture start failed", message);
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
      setCaptureHighMotionRatio(stopResult.quality.highMotionRatio);
      setCaptureTimingGapWarning(stopResult.quality.timingGapWarning);
      setCaptureAlignmentDriftWarning(stopResult.quality.alignmentDriftWarning);
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
          runtime_alignment: stopResult.alignment,
          runtime_quality: {
            quality_score: stopResult.quality.qualityScore,
            quality_status: stopResult.quality.qualityStatus,
            roi_valid_ratio: stopResult.quality.roiValidRatio,
            low_confidence_ratio: stopResult.quality.lowConfidenceRatio,
            high_motion_ratio: stopResult.quality.highMotionRatio,
            timing_gap_warning: stopResult.quality.timingGapWarning,
            alignment_drift_warning: stopResult.quality.alignmentDriftWarning,
          },
        },
      });
      setRuntimeCaptureContractPayload(contractPayload as unknown as Record<string, unknown>);
      setCaptureStatus(
        `Capture stopped. samples=${stopResult.sampleCount}, quality=${stopResult.quality.qualityStatus}, score=${stopResult.quality.qualityScore.toFixed(1)}, high_motion_ratio=${stopResult.quality.highMotionRatio.toFixed(3)}, timing_gap_warning=${stopResult.quality.timingGapWarning ? "yes" : "no"}, alignment_drift_warning=${stopResult.quality.alignmentDriftWarning ? "yes" : "no"}, max_stream_drift_ms=${stopResult.alignment.max_stream_drift_ms ?? "n/a"}`,
      );
      if (stopResult.derived.eventStartTs != null && stopResult.derived.eventEndTs != null) {
        const runtimeNote =
          `runtime_event_start_s=${stopResult.derived.eventStartTs.toFixed(3)}, ` +
          `runtime_event_end_s=${stopResult.derived.eventEndTs.toFixed(3)}`;
        setNotes((existing) => (existing.trim() ? `${existing}; ${runtimeNote}` : runtimeNote));
      }
    } catch (error) {
      setCaptureRunning(false);
      const message = formatSafeExceptionMessage(error);
      setCaptureStatus(`Capture stop failed: ${message}`);
      Alert.alert("Capture stop failed", message);
    }
  }

  function createCurrentRequestHeaderContext(): RequestHeaderContext {
    return requestHeaderContext;
  }

  async function testApiConnection(): Promise<void> {
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      setLastResponse(runtimeReleaseGuard.message);
      Alert.alert("Release guard blocked", runtimeReleaseGuard.message);
      return;
    }
    if (!isClinicalHubPreflightActionAllowed(clinicalHubPreflight)) {
      const message = clinicalHubPreflight.message;
      setLastResponse(message);
      Alert.alert("API preflight blocked", message);
      return;
    }
    const authContextUrl = buildAuthContextUrl(apiBaseUrl);
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
          buildHealthUrl(apiBaseUrl),
          {
            method: "GET",
            headers: buildRequestHeaders(false, createCurrentRequestHeaderContext()),
          },
          requestTimeoutMs,
        );
        if (!healthResponse.ok) {
          setLastResponse(buildHealthCheckFailedMessage(healthResponse.status));
          Alert.alert("API check failed", `HTTP ${healthResponse.status}`);
          return;
        }
        setLastResponse("API reachable (health endpoint).");
        Alert.alert("API reachable", "Health check succeeded.");
        return;
      }
      if (!response.ok) {
        const body = await response.text();
        setLastResponse(buildAuthContextCheckFailedMessage(response.status, body));
        Alert.alert("API check failed", `HTTP ${response.status}`);
        return;
      }
      const body = await response.text();
      const authContext = JSON.parse(body) as AuthContextResponse;
      const message = buildAuthContextOkMessage(authContext);
      setLastResponse(message);
      Alert.alert("API reachable", message);
    } catch (error) {
      const message = buildApiCheckFailedMessage(error);
      setLastResponse(message);
      Alert.alert("API check failed", message);
    }
  }

  function validateRequired(): string | null {
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      return runtimeReleaseGuard.message;
    }
    if (!isClinicalHubPreflightActionAllowed(clinicalHubPreflight)) {
      return clinicalHubPreflight.message;
    }
    return validatePairedPayloadForSubmission(payload, {
      captureRunning,
      runtimeCaptureContractPayload,
    });
  }

  async function syncPendingQueueWithConfiguredApi(): Promise<void> {
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      setLastResponse(runtimeReleaseGuard.message);
      Alert.alert("Release guard blocked", runtimeReleaseGuard.message);
      return;
    }
    if (!isClinicalHubPreflightActionAllowed(clinicalHubPreflight)) {
      const message = clinicalHubPreflight.message;
      setLastResponse(message);
      Alert.alert("API preflight blocked", message);
      return;
    }
    await syncPendingSubmissions();
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
      const pairedRequestHeaderContext: RequestHeaderContext = {
        ...requestHeaderContext,
        request_id: createRequestId(),
      };
      const result = await attemptSubmitEndpoint({
        apiBaseUrl,
        requestTimeoutMs,
        endpoint: "paired_measurements",
        endpointPayload: payload,
        headerContext: pairedRequestHeaderContext,
      });
      if (result.ok) {
        const pairedMeasurementId = extractCreatedRecordId(result.body);
        const capturePayload = buildCapturePackagePayloadFromPaired({
          currentPayload: payload,
          pairedMeasurementId,
          runtimeCaptureContractPayload,
          platformVersion: String(Platform.Version),
        });
        const captureRequestHeaderContext: RequestHeaderContext = {
          ...requestHeaderContext,
          request_id: createRequestId(),
        };
        const captureResult = await attemptSubmitEndpoint({
          apiBaseUrl,
          requestTimeoutMs,
          endpoint: "capture_packages",
          endpointPayload: capturePayload,
          headerContext: captureRequestHeaderContext,
        });
        if (!captureResult.ok) {
          if (captureResult.retryable) {
            await enqueuePendingJob(
              "capture_packages",
              capturePayload,
              captureRequestHeaderContext,
              captureResult.body,
              captureResult.statusCode,
            );
            const queuedMessage = buildQueuedCapturePackageMessage(captureResult);
            setLastResponse(queuedMessage);
            Alert.alert("Submitted with queued capture", queuedMessage);
          } else {
            const warningMessage = buildRejectedCapturePackageMessage(captureResult);
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
        setCaptureHighMotionRatio(0);
        setRuntimeFlowSeries([]);
        setCaptureStatus("Idle");
        setSessionId(createSessionId());
        setSyncId(createSyncId());
        return;
      }

      if (!result.retryable) {
        const nonRetryableMessage = buildNonRetryableUploadMessage(result);
        setLastResponse(nonRetryableMessage);
        Alert.alert(
          "Upload rejected",
          "Request is non-retryable. Check payload, API key, and required fields.",
        );
        return;
      }

      const capturePayloadWithoutPair = buildCapturePackagePayloadFromPaired({
        currentPayload: payload,
        pairedMeasurementId: null,
        runtimeCaptureContractPayload,
        platformVersion: String(Platform.Version),
      });
      const captureRetryHeaderContext: RequestHeaderContext = {
        ...requestHeaderContext,
        request_id: createRequestId(),
      };
      await enqueuePendingJob(
        "paired_measurements",
        payload,
        pairedRequestHeaderContext,
        result.body,
        result.statusCode,
      );
      await enqueuePendingJob(
        "capture_packages",
        capturePayloadWithoutPair,
        captureRetryHeaderContext,
        "queued_with_paired_retry",
        null,
      );
      setLastResponse(buildQueuedPairedAndCaptureMessage(result));
      Alert.alert(
        "Saved offline",
        "No successful upload now. Paired and capture records added to pending queue.",
      );
      setRuntimeCaptureContractPayload(null);
      setCaptureSampleCount(0);
      setCaptureAvgMotionNorm(0);
      setCaptureRoiValidRatio(0);
      setCaptureLowConfidenceRatio(0);
      setCaptureHighMotionRatio(0);
      setRuntimeFlowSeries([]);
      setCaptureStatus("Idle");
      setSessionId(createSessionId());
      setSyncId(createSyncId());
    } finally {
      setSubmitting(false);
    }
  }

  async function loadComparisonSummary() {
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      setSummary(null);
      setSummaryError(runtimeReleaseGuard.message);
      return;
    }
    if (!isClinicalHubPreflightActionAllowed(clinicalHubPreflight)) {
      setSummary(null);
      setSummaryError(clinicalHubPreflight.message);
      return;
    }
    const url = buildComparisonSummaryUrl({
      apiBaseUrl,
      siteId,
      summarySyncId,
      summaryQualityStatus,
    });

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
        setSummaryError(formatSafeResponseProblem(response.status, body));
        return;
      }
      setSummary(JSON.parse(body) as ComparisonSummaryResponse);
    } catch (error) {
      setSummary(null);
      setSummaryError(formatSafeResponseProblem(null, String(error), "NETWORK"));
    } finally {
      setSummaryLoading(false);
    }
  }

  async function loadCaptureCoverageSummary() {
    if (!isRuntimeReleaseGuardActionAllowed(runtimeReleaseGuard)) {
      setCoverageSummary(null);
      setCoverageError(runtimeReleaseGuard.message);
      return;
    }
    if (!isClinicalHubPreflightActionAllowed(clinicalHubPreflight)) {
      setCoverageSummary(null);
      setCoverageError(clinicalHubPreflight.message);
      return;
    }
    const url = buildCaptureCoverageSummaryUrl({
      apiBaseUrl,
      siteId,
      summarySyncId,
      summaryQualityStatus,
    });

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
        setCoverageError(formatSafeResponseProblem(response.status, body));
        return;
      }
      setCoverageSummary(JSON.parse(body) as CaptureCoverageSummaryResponse);
    } catch (error) {
      setCoverageSummary(null);
      setCoverageError(formatSafeResponseProblem(null, String(error), "NETWORK"));
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

        <ClinicalClaimsNotice />

        <ReleaseIdentitySection
          appModelId={appModelId}
          appVersion={appVersion}
          captureMode={captureMode}
          platform={platform}
        />

        <ApiConnectionSection
          apiBaseUrl={apiBaseUrl}
          apiKey={apiKey}
          actorRole={actorRole}
          requestTimeoutMs={requestTimeoutMs}
          clinicalHubPreflightMessage={clinicalHubPreflight.message}
          clinicalHubPreflightStatus={clinicalHubPreflight.status}
          pendingQueue={pendingQueue}
          syncingPending={syncingPending}
          syncStatusMessage={syncStatusMessage}
          onApiBaseUrlChange={setApiBaseUrl}
          onApiKeyChange={setApiKey}
          onActorRoleChange={setActorRole}
          onRequestTimeoutMsChange={setRequestTimeoutMs}
          onTestApiConnection={testApiConnection}
          onSyncPendingSubmissions={syncPendingQueueWithConfiguredApi}
          onClearPendingSubmissions={clearPendingSubmissions}
        />

        <RuntimeCaptureSection
          cameraPermissionGranted={cameraPermission?.granted ?? false}
          cameraPreviewReady={cameraPreviewReady}
          cameraPreviewRef={cameraPreviewRef}
          captureAvgMotionNorm={captureAvgMotionNorm}
          captureHighMotionRatio={captureHighMotionRatio}
          captureAlignmentDriftWarning={captureAlignmentDriftWarning}
          captureLowConfidenceRatio={captureLowConfidenceRatio}
          captureRoiValidRatio={captureRoiValidRatio}
          captureTimingGapWarning={captureTimingGapWarning}
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
          onToggleRoiLock={toggleRoiLock}
        />

        <MeasurementFormSection
          appFlowTime={appFlowTime}
          appModelId={appModelId}
          appQavg={appQavg}
          appQmax={appQmax}
          appQualityScore={appQualityScore}
          appQualityStatus={appQualityStatus}
          appTqmax={appTqmax}
          appVersion={appVersion}
          appVvoid={appVvoid}
          attemptNumber={attemptNumber}
          captureMode={captureMode}
          captureModeSubmissionWarning={captureModeSubmissionWarning}
          deviceModel={deviceModel}
          measuredAt={measuredAt}
          notes={notes}
          operatorId={operatorId}
          platform={platform}
          qualitySubmissionWarning={qualitySubmissionWarning}
          refDeviceModel={refDeviceModel}
          refDeviceSerial={refDeviceSerial}
          refFlowTime={refFlowTime}
          refQavg={refQavg}
          refQmax={refQmax}
          refTqmax={refTqmax}
          refVvoid={refVvoid}
          sessionId={sessionId}
          siteId={siteId}
          subjectId={subjectId}
          submitting={submitting}
          syncId={syncId}
          onAppFlowTimeChange={setAppFlowTime}
          onAppModelIdChange={setAppModelId}
          onAppQavgChange={setAppQavg}
          onAppQmaxChange={setAppQmax}
          onAppQualityScoreChange={setAppQualityScore}
          onAppQualityStatusChange={setAppQualityStatus}
          onAppTqmaxChange={setAppTqmax}
          onAppVersionChange={setAppVersion}
          onAppVvoidChange={setAppVvoid}
          onAttemptNumberChange={setAttemptNumber}
          onCaptureModeChange={setCaptureMode}
          onDeviceModelChange={setDeviceModel}
          onMeasuredAtChange={setMeasuredAt}
          onNotesChange={setNotes}
          onOperatorIdChange={setOperatorId}
          onPlatformChange={setPlatform}
          onRefDeviceModelChange={setRefDeviceModel}
          onRefDeviceSerialChange={setRefDeviceSerial}
          onRefFlowTimeChange={setRefFlowTime}
          onRefQavgChange={setRefQavg}
          onRefQmaxChange={setRefQmax}
          onRefTqmaxChange={setRefTqmax}
          onRefVvoidChange={setRefVvoid}
          onSessionIdChange={setSessionId}
          onSiteIdChange={setSiteId}
          onSubjectIdChange={setSubjectId}
          onSubmit={submitPayload}
          onSyncIdChange={setSyncId}
        />

        <ResponseAndSummarySection
          coverageError={coverageError}
          coverageLoading={coverageLoading}
          coverageSummary={coverageSummary}
          lastResponse={lastResponse}
          summary={summary}
          summaryError={summaryError}
          summaryLoading={summaryLoading}
          summaryQualityStatus={summaryQualityStatus}
          summarySyncId={summarySyncId}
          onLoadBothSummaries={loadBothSummaries}
          onLoadCaptureCoverageSummary={loadCaptureCoverageSummary}
          onLoadComparisonSummary={loadComparisonSummary}
          onSummaryQualityStatusChange={setSummaryQualityStatus}
          onSummarySyncIdChange={setSummarySyncId}
        />
      </ScrollView>
    </SafeAreaView>
  );
}
