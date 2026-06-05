import type { SubmitAttemptResult } from "../types";

function formatAttemptProblem(
  result: SubmitAttemptResult,
  fallbackStatusLabel: "ERROR" | "NETWORK",
): string {
  return `${result.statusCode ? `HTTP ${result.statusCode}` : fallbackStatusLabel} ${result.body}`;
}

export function buildQueuedCapturePackageMessage(
  result: SubmitAttemptResult,
): string {
  return `Paired uploaded; capture package queued for retry: ${formatAttemptProblem(
    result,
    "NETWORK",
  )}`;
}

export function buildRejectedCapturePackageMessage(
  result: SubmitAttemptResult,
): string {
  return `Paired measurement uploaded, but capture package rejected: ${formatAttemptProblem(
    result,
    "ERROR",
  )}`;
}

export function buildNonRetryableUploadMessage(
  result: SubmitAttemptResult,
): string {
  return `Upload rejected and not queued. ${formatAttemptProblem(result, "ERROR")}`;
}

export function buildQueuedPairedAndCaptureMessage(
  result: SubmitAttemptResult,
): string {
  return `Queued paired+capture for retry. Last paired error: ${formatAttemptProblem(
    result,
    "NETWORK",
  )}`;
}
