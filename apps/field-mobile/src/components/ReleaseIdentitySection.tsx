import React from "react";
import { Text, View } from "react-native";

import { styles } from "../styles/appStyles";
import { buildReleaseIdentitySnapshot } from "../utils/releaseIdentity";

type ReleaseIdentitySectionProps = {
  appVersion: string;
  appModelId: string;
  captureMode: string;
  platform: string;
};

export function ReleaseIdentitySection({
  appVersion,
  appModelId,
  captureMode,
  platform,
}: ReleaseIdentitySectionProps) {
  const snapshot = buildReleaseIdentitySnapshot({
    platform,
    payloadAppVersion: appVersion,
    payloadModelId: appModelId,
    payloadCaptureMode: captureMode,
  });
  const statusStyle =
    snapshot.payloadStatus === "aligned"
      ? styles.releaseIdentityGoodText
      : styles.releaseIdentityWarningText;

  return (
    <View style={styles.releaseIdentityBox}>
      <Text style={styles.sectionTitle}>Release Identity</Text>
      {snapshot.canonicalRows.map((row) => (
        <Text key={row.label} style={styles.releaseIdentityText}>
          {row.label}: {row.value}
        </Text>
      ))}
      <Text style={[styles.releaseIdentityText, statusStyle]}>
        Payload traceability: {snapshot.payloadStatus}
      </Text>
      <Text style={styles.releaseIdentityText}>{snapshot.payloadEvidence}</Text>
      <Text style={styles.helperText}>{snapshot.artifactTraceabilityNote}</Text>
    </View>
  );
}
