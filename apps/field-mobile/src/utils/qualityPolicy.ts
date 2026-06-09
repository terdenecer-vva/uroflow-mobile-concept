import type { QualityStatus } from "../types";

const QUALITY_SEVERITY: Record<QualityStatus, number> = {
  valid: 0,
  repeat: 1,
  reject: 2,
};

export function isQualityStatus(value: unknown): value is QualityStatus {
  return value === "valid" || value === "repeat" || value === "reject";
}

function runtimeQualityFromAnalysis(analysis: unknown): QualityStatus | null {
  if (!analysis || typeof analysis !== "object" || !("runtime_quality" in analysis)) {
    return null;
  }
  const runtimeQuality = (analysis as { runtime_quality?: unknown }).runtime_quality;
  if (!runtimeQuality || typeof runtimeQuality !== "object") {
    return null;
  }
  const qualityStatus = (runtimeQuality as { quality_status?: unknown }).quality_status;
  return isQualityStatus(qualityStatus) ? qualityStatus : null;
}

export function extractRuntimeQualityStatus(
  runtimeCaptureContractPayload: Record<string, unknown> | null | undefined,
): QualityStatus | null {
  if (!runtimeCaptureContractPayload) {
    return null;
  }
  return runtimeQualityFromAnalysis(runtimeCaptureContractPayload.analysis);
}

export function buildRuntimeQualitySubmissionError(
  appQualityStatus: unknown,
  runtimeCaptureContractPayload: Record<string, unknown> | null | undefined,
): string | null {
  if (!isQualityStatus(appQualityStatus)) {
    return "quality_status must be valid, repeat, or reject";
  }

  const runtimeQualityStatus = extractRuntimeQualityStatus(runtimeCaptureContractPayload);
  if (!runtimeQualityStatus) {
    return null;
  }

  if (QUALITY_SEVERITY[appQualityStatus] < QUALITY_SEVERITY[runtimeQualityStatus]) {
    return (
      `Runtime capture quality is ${runtimeQualityStatus}; app quality_status cannot be ` +
      `${appQualityStatus}. Keep ${runtimeQualityStatus} or repeat capture before submission.`
    );
  }
  return null;
}

export function buildLowQualitySubmissionWarning(
  appQualityStatus: QualityStatus,
  runtimeCaptureContractPayload: Record<string, unknown> | null | undefined,
): string | null {
  const runtimeQualityStatus = extractRuntimeQualityStatus(runtimeCaptureContractPayload);
  const mostSevereStatus =
    runtimeQualityStatus &&
    QUALITY_SEVERITY[runtimeQualityStatus] > QUALITY_SEVERITY[appQualityStatus]
      ? runtimeQualityStatus
      : appQualityStatus;

  if (mostSevereStatus === "valid") {
    return null;
  }

  if (mostSevereStatus === "reject") {
    return (
      "Low-quality warning: quality_status=reject. Do not treat this capture as clinical " +
      "evidence; repeat capture before comparison unless retaining it for audit traceability."
    );
  }

  return (
    "Low-quality warning: quality_status=repeat. Repeat capture before clinical comparison " +
    "when feasible; keep repeat status visible if uploaded for traceability."
  );
}
