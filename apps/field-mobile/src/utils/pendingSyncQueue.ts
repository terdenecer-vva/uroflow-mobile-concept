import type {
  PendingSubmission,
  RequestHeaderContext,
  SubmitAttemptResult,
} from "../types";
import { summarizePendingError } from "./appHelpers";

export const MAX_PENDING_SYNC_BATCH_SIZE = 10;

export type PendingSyncItemOutcome =
  | "synced_paired"
  | "synced_capture"
  | "retryable"
  | "dropped_non_retryable";

export type PendingSyncAttempt = {
  attemptedItem: PendingSubmission;
  outcome: PendingSyncItemOutcome;
};

export type PendingSyncStatusSummary = {
  batchCount: number;
  totalCount: number;
  syncedPaired: number;
  syncedCapture: number;
  remainingQueued: number;
  deferred: number;
  droppedNonRetryable: number;
};

export type PendingAutoSyncGate = {
  settingsHydrated: boolean;
  pendingCount: number;
  apiConfigured: boolean;
};

export type PendingConnectivityRestoreGate = PendingAutoSyncGate & {
  wasNetworkReachable: boolean | null;
  isNetworkReachable: boolean;
};

export function splitPendingSyncBatch(
  queue: PendingSubmission[],
  maxBatchSize = MAX_PENDING_SYNC_BATCH_SIZE,
): { batch: PendingSubmission[]; deferred: PendingSubmission[] } {
  const batchSize = Number.isFinite(maxBatchSize)
    ? Math.max(0, Math.floor(maxBatchSize))
    : MAX_PENDING_SYNC_BATCH_SIZE;
  return {
    batch: queue.slice(0, batchSize),
    deferred: queue.slice(batchSize),
  };
}

export function shouldAutoSyncPendingQueue(gate: PendingAutoSyncGate): boolean {
  return gate.settingsHydrated && gate.pendingCount > 0 && gate.apiConfigured;
}

export function isNetworkReachableForSync(
  isConnected: boolean | null,
  isInternetReachable: boolean | null,
): boolean {
  return isConnected === true && isInternetReachable !== false;
}

export function shouldAutoSyncOnConnectivityRestore(
  gate: PendingConnectivityRestoreGate,
): boolean {
  return (
    shouldAutoSyncPendingQueue(gate) &&
    gate.wasNetworkReachable === false &&
    gate.isNetworkReachable
  );
}

export function buildPendingSyncAttempt(options: {
  item: PendingSubmission;
  headerContext: RequestHeaderContext;
  result: SubmitAttemptResult;
  attemptedAtIso: string;
}): PendingSyncAttempt {
  const attemptCount = Number.isFinite(options.item.attempt_count)
    ? Math.max(0, Math.floor(options.item.attempt_count))
    : 0;
  const attemptedItem: PendingSubmission = {
    ...options.item,
    request_headers: options.headerContext,
    attempt_count: attemptCount + 1,
    last_attempt_at: options.attemptedAtIso,
    last_status_code: options.result.statusCode,
    last_error: options.result.ok
      ? null
      : summarizePendingError(options.result.body) ?? "server_or_client_response",
  };

  if (options.result.ok) {
    return {
      attemptedItem,
      outcome:
        options.item.endpoint === "capture_packages" ? "synced_capture" : "synced_paired",
    };
  }

  return {
    attemptedItem,
    outcome: options.result.retryable ? "retryable" : "dropped_non_retryable",
  };
}

export function buildPendingSyncStatusMessage(summary: PendingSyncStatusSummary): string {
  return (
    `Sync batch completed (${summary.batchCount}/${summary.totalCount}). ` +
    `Synced paired: ${summary.syncedPaired}, synced capture: ${summary.syncedCapture}, ` +
    `remaining queued: ${summary.remainingQueued}, ` +
    `deferred: ${summary.deferred}, dropped non-retryable: ${summary.droppedNonRetryable}.`
  );
}
