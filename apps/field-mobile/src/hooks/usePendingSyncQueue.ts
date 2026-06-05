import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, AppState } from "react-native";

import { attemptSubmitEndpoint } from "../api/clinicalHub";
import {
  loadPendingSubmissions,
  savePendingSubmissions,
} from "../storage/appStorage";
import type {
  EndpointPayload,
  PendingEndpoint,
  PendingSubmission,
  RequestHeaderContext,
} from "../types";
import { createPendingId, resolvePendingHeaderContext } from "../utils/appHelpers";
import {
  buildPendingSyncAttempt,
  buildPendingSyncStatusMessage,
  splitPendingSyncBatch,
} from "../utils/pendingSyncQueue";

type UsePendingSyncQueueOptions = {
  apiBaseUrl: string;
  requestTimeoutMs: string;
  requestHeaderContext: RequestHeaderContext;
  settingsHydrated: boolean;
  onLastResponse: (message: string) => void;
};

export function usePendingSyncQueue({
  apiBaseUrl,
  requestTimeoutMs,
  requestHeaderContext,
  settingsHydrated,
  onLastResponse,
}: UsePendingSyncQueueOptions) {
  const [pendingQueue, setPendingQueue] = useState<PendingSubmission[]>([]);
  const [syncingPending, setSyncingPending] = useState(false);
  const [syncStatusMessage, setSyncStatusMessage] = useState("");
  const syncInFlightRef = useRef(false);
  const autoSyncIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const persistPendingQueue = useCallback(async (queue: PendingSubmission[]): Promise<void> => {
    await savePendingSubmissions(queue);
    setPendingQueue(queue);
  }, []);

  const enqueuePendingJob = useCallback(
    async (
      endpoint: PendingEndpoint,
      endpointPayload: EndpointPayload,
      headerContext: RequestHeaderContext,
      lastError: string | null,
      lastStatusCode: number | null,
    ): Promise<void> => {
      const queue = await loadPendingSubmissions();
      const pendingId = createPendingId();
      const pendingItem: PendingSubmission = {
        id: pendingId,
        created_at: new Date().toISOString(),
        endpoint,
        payload: endpointPayload,
        request_headers: {
          ...headerContext,
          request_id: headerContext.request_id || pendingId,
        },
        attempt_count: 0,
        last_attempt_at: null,
        last_error: lastError,
        last_status_code: lastStatusCode,
      };
      await persistPendingQueue([...queue, pendingItem]);
    },
    [persistPendingQueue],
  );

  const syncPendingSubmissions = useCallback(
    async (showAlert = true): Promise<void> => {
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

        const { batch, deferred } = splitPendingSyncBatch(queue);
        const retryableBatchItems: PendingSubmission[] = [];
        let syncedPaired = 0;
        let syncedCapture = 0;
        let droppedNonRetryable = 0;

        for (const item of batch) {
          const headerContext = resolvePendingHeaderContext(item, requestHeaderContext);
          const result = await attemptSubmitEndpoint({
            apiBaseUrl,
            requestTimeoutMs,
            endpoint: item.endpoint,
            endpointPayload: item.payload,
            headerContext,
          });
          const attempt = buildPendingSyncAttempt({
            item,
            headerContext,
            result,
            attemptedAtIso: new Date().toISOString(),
          });
          if (attempt.outcome === "synced_capture") {
            syncedCapture += 1;
            continue;
          }
          if (attempt.outcome === "synced_paired") {
            syncedPaired += 1;
            continue;
          }
          if (attempt.outcome === "retryable") {
            retryableBatchItems.push(attempt.attemptedItem);
            continue;
          }
          droppedNonRetryable += 1;
        }

        const remaining = [...retryableBatchItems, ...deferred];
        await persistPendingQueue(remaining);

        const statusMessage = buildPendingSyncStatusMessage({
          batchCount: batch.length,
          totalCount: queue.length,
          syncedPaired,
          syncedCapture,
          remainingQueued: remaining.length,
          deferred: deferred.length,
          droppedNonRetryable,
        });
        setSyncStatusMessage(statusMessage);
        onLastResponse(statusMessage);
        if (showAlert) {
          Alert.alert("Sync completed", statusMessage);
        }
      } finally {
        syncInFlightRef.current = false;
        setSyncingPending(false);
      }
    },
    [
      apiBaseUrl,
      onLastResponse,
      persistPendingQueue,
      requestHeaderContext,
      requestTimeoutMs,
    ],
  );

  const clearPendingSubmissions = useCallback(async (): Promise<void> => {
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
  }, [persistPendingQueue]);

  useEffect(() => {
    void (async () => {
      setPendingQueue(await loadPendingSubmissions());
    })();
  }, []);

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
  }, [pendingQueue.length, settingsHydrated, syncPendingSubmissions]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active" && pendingQueue.length > 0) {
        void syncPendingSubmissions(false);
      }
    });
    return () => {
      subscription.remove();
    };
  }, [pendingQueue.length, syncPendingSubmissions]);

  return {
    pendingQueue,
    syncingPending,
    syncStatusMessage,
    enqueuePendingJob,
    syncPendingSubmissions,
    clearPendingSubmissions,
  };
}
