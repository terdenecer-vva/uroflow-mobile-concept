import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, AppState } from "react-native";
import NetInfo from "@react-native-community/netinfo";

import {
  attemptSubmitEndpoint,
  buildMissingApiBaseUrlMessage,
  isConfiguredApiBaseUrl,
} from "../api/clinicalHub";
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
import { createPendingId, summarizePendingError } from "../utils/appHelpers";
import {
  isNetworkReachableForSync,
  runPendingSyncBatch,
  shouldAutoSyncPendingQueue,
  shouldAutoSyncOnConnectivityRestore,
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
  const networkReachableRef = useRef<boolean | null>(null);
  const apiConfigured = isConfiguredApiBaseUrl(apiBaseUrl);

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
      const storedLastError = lastError
        ? summarizePendingError(lastError) ?? "server_or_client_response"
        : null;
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
        last_error: storedLastError,
        last_status_code: lastStatusCode,
      };
      await persistPendingQueue([...queue, pendingItem]);
    },
    [persistPendingQueue],
  );

  const syncPendingSubmissions = useCallback(
    async (showAlert = true): Promise<void> => {
      if (!apiConfigured) {
        const message = buildMissingApiBaseUrlMessage();
        setSyncStatusMessage(message);
        onLastResponse(message);
        if (showAlert) {
          Alert.alert("API URL required", message);
        }
        return;
      }
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

        const syncResult = await runPendingSyncBatch({
          queue,
          requestHeaderContext,
          submitEndpoint: ({ endpoint, endpointPayload, headerContext }) =>
            attemptSubmitEndpoint({
              apiBaseUrl,
              requestTimeoutMs,
              endpoint,
              endpointPayload,
              headerContext,
            }),
        });
        await persistPendingQueue(syncResult.remaining);

        setSyncStatusMessage(syncResult.statusMessage);
        onLastResponse(syncResult.statusMessage);
        if (showAlert) {
          Alert.alert("Sync completed", syncResult.statusMessage);
        }
      } finally {
        syncInFlightRef.current = false;
        setSyncingPending(false);
      }
    },
    [
      apiConfigured,
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
    const shouldAutoSync = shouldAutoSyncPendingQueue({
      settingsHydrated,
      pendingCount: pendingQueue.length,
      apiConfigured,
    });

    if (!shouldAutoSync) {
      if (autoSyncIntervalRef.current != null) {
        clearInterval(autoSyncIntervalRef.current);
        autoSyncIntervalRef.current = null;
      }
      if (settingsHydrated && pendingQueue.length > 0 && !apiConfigured) {
        setSyncStatusMessage(buildMissingApiBaseUrlMessage());
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
  }, [apiConfigured, pendingQueue.length, settingsHydrated, syncPendingSubmissions]);

  useEffect(() => {
    const unsubscribe = NetInfo.addEventListener((state) => {
      const isNetworkReachable = isNetworkReachableForSync(
        state.isConnected,
        state.isInternetReachable,
      );
      const wasNetworkReachable = networkReachableRef.current;
      networkReachableRef.current = isNetworkReachable;

      if (
        shouldAutoSyncOnConnectivityRestore({
          settingsHydrated,
          pendingCount: pendingQueue.length,
          apiConfigured,
          wasNetworkReachable,
          isNetworkReachable,
        })
      ) {
        void syncPendingSubmissions(false);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [apiConfigured, pendingQueue.length, settingsHydrated, syncPendingSubmissions]);

  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active" && pendingQueue.length > 0 && apiConfigured) {
        void syncPendingSubmissions(false);
      }
    });
    return () => {
      subscription.remove();
    };
  }, [apiConfigured, pendingQueue.length, syncPendingSubmissions]);

  return {
    pendingQueue,
    syncingPending,
    syncStatusMessage,
    enqueuePendingJob,
    syncPendingSubmissions,
    clearPendingSubmissions,
  };
}
