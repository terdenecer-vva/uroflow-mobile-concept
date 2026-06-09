import type { PairedPayload, QualityStatus } from "../types";
import { parseNumber } from "../utils/appHelpers";
import {
  buildCaptureModeSubmissionError,
  normalizeCaptureMode,
} from "../utils/captureModePolicy";
import { buildRuntimeQualitySubmissionError, isQualityStatus } from "../utils/qualityPolicy";

const SUPPORTED_PLATFORMS = ["ios", "android"] as const;

type MetricMap = Record<string, number | null>;

export type PairedPayloadFormValues = {
  sessionId: string;
  syncId: string;
  siteId: string;
  subjectId: string;
  operatorId: string;
  attemptNumber: string;
  measuredAt: string;
  platform: string;
  deviceModel: string;
  appVersion: string;
  captureMode: string;
  appQmax: string;
  appQavg: string;
  appVvoid: string;
  appFlowTime: string;
  appTqmax: string;
  appQualityStatus: QualityStatus;
  appQualityScore: string;
  appModelId: string;
  refQmax: string;
  refQavg: string;
  refVvoid: string;
  refFlowTime: string;
  refTqmax: string;
  refDeviceModel: string;
  refDeviceSerial: string;
  notes: string;
};

export function buildPairedPayloadFromForm(values: PairedPayloadFormValues): PairedPayload {
  return {
    session: {
      session_id: values.sessionId.trim(),
      sync_id: values.syncId.trim() || null,
      site_id: values.siteId.trim(),
      subject_id: values.subjectId.trim(),
      operator_id: values.operatorId.trim(),
      attempt_number: parseNumber(values.attemptNumber),
      measured_at: values.measuredAt.trim(),
      platform: values.platform.trim().toLowerCase(),
      device_model: values.deviceModel.trim() || null,
      app_version: values.appVersion.trim() || null,
      capture_mode: normalizeCaptureMode(values.captureMode),
    },
    app: {
      metrics: {
        qmax_ml_s: parseNumber(values.appQmax),
        qavg_ml_s: parseNumber(values.appQavg),
        vvoid_ml: parseNumber(values.appVvoid),
        flow_time_s: parseNumber(values.appFlowTime),
        tqmax_s: parseNumber(values.appTqmax),
      },
      quality_status: values.appQualityStatus,
      quality_score: parseNumber(values.appQualityScore),
      model_id: values.appModelId.trim() || null,
    },
    reference: {
      metrics: {
        qmax_ml_s: parseNumber(values.refQmax),
        qavg_ml_s: parseNumber(values.refQavg),
        vvoid_ml: parseNumber(values.refVvoid),
        flow_time_s: parseNumber(values.refFlowTime),
        tqmax_s: parseNumber(values.refTqmax),
      },
      device_model: values.refDeviceModel.trim() || null,
      device_serial: values.refDeviceSerial.trim() || null,
    },
    notes: values.notes.trim() || null,
  };
}

function hasFiniteNonNegativeMetric(value: number | null): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function firstMissingMetric(metrics: MetricMap, fields: string[]): string | null {
  return fields.find((field) => !hasFiniteNonNegativeMetric(metrics[field] ?? null)) ?? null;
}

function hasIsoTimestampWithTimezone(value: string): boolean {
  const trimmed = value.trim();
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(
      trimmed,
    )
  ) {
    return false;
  }
  return Number.isFinite(Date.parse(trimmed));
}

export function validatePairedPayloadForSubmission(
  payload: PairedPayload,
  options: {
    captureRunning: boolean;
    runtimeCaptureContractPayload?: Record<string, unknown> | null;
  },
): string | null {
  if (options.captureRunning) {
    return "Stop runtime capture before submitting.";
  }
  if (!isQualityStatus(payload.app.quality_status)) {
    return "quality_status must be valid, repeat, or reject";
  }
  const runtimeQualityError = buildRuntimeQualitySubmissionError(
    payload.app.quality_status,
    options.runtimeCaptureContractPayload,
  );
  if (runtimeQualityError) {
    return runtimeQualityError;
  }
  if (!payload.session.session_id) {
    return "session_id is required";
  }
  if (!payload.session.site_id || !payload.session.subject_id || !payload.session.operator_id) {
    return "site_id, subject_id, operator_id are required";
  }
  if (!payload.session.attempt_number || payload.session.attempt_number < 1) {
    return "attempt_number must be an integer >= 1";
  }
  if (!Number.isInteger(payload.session.attempt_number)) {
    return "attempt_number must be an integer >= 1";
  }
  if (!payload.session.measured_at) {
    return "measured_at is required";
  }
  if (!hasIsoTimestampWithTimezone(payload.session.measured_at)) {
    return "measured_at must be ISO-8601 with timezone";
  }
  if (!SUPPORTED_PLATFORMS.includes(payload.session.platform as (typeof SUPPORTED_PLATFORMS)[number])) {
    return "platform must be ios or android";
  }
  const captureModeError = buildCaptureModeSubmissionError(
    payload.session.capture_mode,
    options.runtimeCaptureContractPayload,
  );
  if (captureModeError) {
    return captureModeError;
  }
  const missingAppMetric = firstMissingMetric(payload.app.metrics, [
    "qmax_ml_s",
    "qavg_ml_s",
    "vvoid_ml",
    "flow_time_s",
    "tqmax_s",
  ]);
  if (missingAppMetric) {
    return "App metrics qmax/qavg/vvoid/flow_time/tqmax must be finite and non-negative";
  }
  const appQmax = payload.app.metrics.qmax_ml_s;
  const appQavg = payload.app.metrics.qavg_ml_s;
  if (
    hasFiniteNonNegativeMetric(appQmax) &&
    hasFiniteNonNegativeMetric(appQavg) &&
    appQmax < appQavg
  ) {
    return "App metric qmax must be >= qavg";
  }
  const qualityScore = payload.app.quality_score;
  if (
    typeof qualityScore !== "number" ||
    !Number.isFinite(qualityScore) ||
    qualityScore < 0 ||
    qualityScore > 100
  ) {
    return "quality_score is required and must be 0-100";
  }
  const missingReferenceMetric = firstMissingMetric(payload.reference.metrics, [
    "qmax_ml_s",
    "qavg_ml_s",
    "vvoid_ml",
    "flow_time_s",
  ]);
  if (missingReferenceMetric) {
    return "Reference metrics qmax/qavg/vvoid/flow_time must be finite and non-negative";
  }
  const refQmax = payload.reference.metrics.qmax_ml_s;
  const refQavg = payload.reference.metrics.qavg_ml_s;
  if (
    hasFiniteNonNegativeMetric(refQmax) &&
    hasFiniteNonNegativeMetric(refQavg) &&
    refQmax < refQavg
  ) {
    return "Reference metric qmax must be >= qavg";
  }
  return null;
}
