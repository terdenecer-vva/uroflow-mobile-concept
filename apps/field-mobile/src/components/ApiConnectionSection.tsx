import React from "react";
import { Pressable, Text, View } from "react-native";

import type { PendingSubmission } from "../types";
import { normalizeActorRoleInput } from "../utils/appHelpers";
import { styles } from "../styles/appStyles";
import { LabeledInput } from "./LabeledInput";
import { PendingQueuePreview } from "./PendingQueuePreview";

type ApiConnectionSectionProps = {
  apiBaseUrl: string;
  apiKey: string;
  actorRole: string;
  requestTimeoutMs: string;
  pendingQueue: PendingSubmission[];
  syncingPending: boolean;
  syncStatusMessage: string;
  onApiBaseUrlChange: (value: string) => void;
  onApiKeyChange: (value: string) => void;
  onActorRoleChange: (value: string) => void;
  onRequestTimeoutMsChange: (value: string) => void;
  onTestApiConnection: () => Promise<void>;
  onSyncPendingSubmissions: () => Promise<void>;
  onClearPendingSubmissions: () => Promise<void>;
};

export function ApiConnectionSection({
  apiBaseUrl,
  apiKey,
  actorRole,
  requestTimeoutMs,
  pendingQueue,
  syncingPending,
  syncStatusMessage,
  onApiBaseUrlChange,
  onApiKeyChange,
  onActorRoleChange,
  onRequestTimeoutMsChange,
  onTestApiConnection,
  onSyncPendingSubmissions,
  onClearPendingSubmissions,
}: ApiConnectionSectionProps) {
  return (
    <>
      <Text style={styles.sectionTitle}>API</Text>
      <LabeledInput label="API Base URL" value={apiBaseUrl} onChangeText={onApiBaseUrlChange} />
      <LabeledInput
        label="API Key (x-api-key)"
        value={apiKey}
        onChangeText={onApiKeyChange}
        secureTextEntry
      />
      <LabeledInput
        label="Actor Role (x-actor-role)"
        value={actorRole}
        onChangeText={(value) => onActorRoleChange(normalizeActorRoleInput(value))}
      />
      <LabeledInput
        label="Request Timeout (ms)"
        value={requestTimeoutMs}
        onChangeText={onRequestTimeoutMsChange}
        keyboardType="number-pad"
      />
      <PendingQueuePreview pendingQueue={pendingQueue} />
      <View style={styles.buttonRow}>
        <Pressable
          style={[styles.summaryButton, styles.buttonGrow]}
          onPress={() => void onTestApiConnection()}
        >
          <Text style={styles.submitButtonText}>Test API</Text>
        </Pressable>
        <Pressable
          style={[
            styles.summaryButton,
            styles.buttonGrow,
            syncingPending && styles.submitButtonDisabled,
          ]}
          onPress={() => void onSyncPendingSubmissions()}
          disabled={syncingPending}
        >
          <Text style={styles.submitButtonText}>
            {syncingPending ? "Syncing..." : "Sync Queue"}
          </Text>
        </Pressable>
        <Pressable
          style={[styles.dangerButton, styles.buttonGrow]}
          onPress={() => void onClearPendingSubmissions()}
        >
          <Text style={styles.submitButtonText}>Clear Queue</Text>
        </Pressable>
      </View>
      {syncStatusMessage ? (
        <Text style={styles.syncStatusText}>{syncStatusMessage}</Text>
      ) : null}
    </>
  );
}
