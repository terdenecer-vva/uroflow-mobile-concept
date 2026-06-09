import type { PairedPayload, QualityStatus } from "../types";
import { parseNumber } from "../utils/appHelpers";
import { buildRuntimeQualitySubmissionError, isQualityStatus } from "../utils/qualityPolicy";

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
      platform: values.platform,
      device_model: values.deviceModel.trim() || null,
      app_version: values.appVersion.trim() || null,
      capture_mode: values.captureMode,
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
    return "attempt_number must be >= 1";
  }
  if (!payload.session.measured_at) {
    return "measured_at is required";
  }
  if (
    payload.app.metrics.qmax_ml_s == null ||
    payload.app.metrics.qavg_ml_s == null ||
    payload.app.metrics.vvoid_ml == null
  ) {
    return "App metrics qmax/qavg/vvoid are required";
  }
  if (
    payload.reference.metrics.qmax_ml_s == null ||
    payload.reference.metrics.qavg_ml_s == null ||
    payload.reference.metrics.vvoid_ml == null
  ) {
    return "Reference metrics qmax/qavg/vvoid are required";
  }
  return null;
}
