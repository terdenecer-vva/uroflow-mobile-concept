import React from "react";
import { Text, View } from "react-native";

import type { PendingSubmission } from "../types";
import { summarizePendingError } from "../utils/appHelpers";
import { styles } from "../styles/appStyles";

type PendingQueuePreviewProps = {
  pendingQueue: PendingSubmission[];
};

export function PendingQueuePreview({ pendingQueue }: PendingQueuePreviewProps) {
  return (
    <>
      <View style={styles.pendingRow}>
        <Text style={styles.pendingText}>Pending submissions: {pendingQueue.length}</Text>
      </View>
      {pendingQueue.slice(0, 3).map((item) => {
        const errorSummary = summarizePendingError(item.last_error);
        return (
          <Text key={item.id} style={styles.pendingItemText}>
            {item.id}: endpoint={item.endpoint}, attempts={item.attempt_count}
            {item.payload.session.sync_id ? `, sync=${item.payload.session.sync_id}` : ""}
            {item.request_headers.site_id ? `, site=${item.request_headers.site_id}` : ""}
            {item.request_headers.actor_role ? `, role=${item.request_headers.actor_role}` : ""}
            {item.last_attempt_at ? `, last_attempt=${item.last_attempt_at}` : ""}
            {item.last_status_code != null ? `, last_status=${item.last_status_code}` : ""}
            {errorSummary ? `, last_error=${errorSummary}` : ""}
          </Text>
        );
      })}
      {pendingQueue.length > 3 ? (
        <Text style={styles.pendingItemText}>
          ...and {pendingQueue.length - 3} more pending submissions
        </Text>
      ) : null}
    </>
  );
}
