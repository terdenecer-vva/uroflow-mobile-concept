import { APP_DEFAULT_CAPTURE_MODE } from "../config/appConfig";

export const SUPPORTED_PILOT_CAPTURE_MODE = APP_DEFAULT_CAPTURE_MODE;

export function normalizeCaptureMode(value: unknown): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function isSupportedPilotCaptureMode(value: unknown): boolean {
  return normalizeCaptureMode(value) === SUPPORTED_PILOT_CAPTURE_MODE;
}

export function extractRuntimeCaptureMode(
  runtimeCaptureContractPayload: Record<string, unknown> | null | undefined,
): string | null {
  if (!runtimeCaptureContractPayload) {
    return null;
  }
  const session = runtimeCaptureContractPayload.session;
  if (!session || typeof session !== "object" || !("mode" in session)) {
    return null;
  }
  const mode = normalizeCaptureMode((session as { mode?: unknown }).mode);
  return mode || null;
}

export function buildCaptureModeSubmissionError(
  value: unknown,
  runtimeCaptureContractPayload?: Record<string, unknown> | null,
): string | null {
  const normalizedCaptureMode = normalizeCaptureMode(value);
  if (!normalizedCaptureMode) {
    return `capture_mode is required; pilot submissions must use ${SUPPORTED_PILOT_CAPTURE_MODE}.`;
  }
  if (!isSupportedPilotCaptureMode(normalizedCaptureMode)) {
    return (
      `capture_mode must be ${SUPPORTED_PILOT_CAPTURE_MODE} for pilot submissions; ` +
      "repeat using the water-impact SOP before submission."
    );
  }

  const runtimeCaptureMode = extractRuntimeCaptureMode(runtimeCaptureContractPayload);
  if (runtimeCaptureMode && !isSupportedPilotCaptureMode(runtimeCaptureMode)) {
    return (
      `Runtime capture mode is ${runtimeCaptureMode}; capture_mode must be ` +
      `${SUPPORTED_PILOT_CAPTURE_MODE} for pilot submissions. Repeat capture using the ` +
      "water-impact SOP before submission."
    );
  }
  return null;
}

export function buildCaptureModeSubmissionWarning(value: unknown): string | null {
  const normalizedCaptureMode = normalizeCaptureMode(value);
  if (!normalizedCaptureMode) {
    return `Capture mode warning: set capture_mode=${SUPPORTED_PILOT_CAPTURE_MODE} before submission.`;
  }
  if (isSupportedPilotCaptureMode(normalizedCaptureMode)) {
    return null;
  }
  return (
    `Capture mode warning: ${normalizedCaptureMode} is outside the validated ` +
    `${SUPPORTED_PILOT_CAPTURE_MODE} pilot workflow. Repeat capture using the water-impact SOP.`
  );
}
