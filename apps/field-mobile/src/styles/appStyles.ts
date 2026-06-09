import { StyleSheet } from "react-native";

export const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#f6f7f8",
  },
  container: {
    padding: 16,
    paddingBottom: 40,
  },
  title: {
    fontSize: 24,
    fontWeight: "700",
    color: "#15202b",
  },
  subtitle: {
    marginTop: 4,
    marginBottom: 16,
    color: "#475467",
  },
  helperText: {
    marginBottom: 10,
    fontSize: 12,
    color: "#334155",
  },
  claimsNoticeBox: {
    marginBottom: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#0f766e",
    backgroundColor: "#ecfdf5",
    padding: 12,
  },
  claimsNoticeKicker: {
    color: "#0f766e",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.8,
    marginBottom: 4,
    textTransform: "uppercase",
  },
  claimsNoticeTitle: {
    color: "#0f172a",
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 6,
  },
  claimsNoticeText: {
    color: "#134e4a",
    fontSize: 12,
    marginBottom: 6,
  },
  claimsNoticeBullet: {
    color: "#134e4a",
    fontSize: 12,
    marginTop: 2,
  },
  qualityWarningBox: {
    marginTop: 4,
    marginBottom: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#f59e0b",
    backgroundColor: "#fffbeb",
    padding: 10,
  },
  qualityWarningText: {
    color: "#92400e",
    fontSize: 12,
    fontWeight: "600",
  },
  preflightBox: {
    marginTop: 2,
    marginBottom: 10,
    borderRadius: 8,
    borderWidth: 1,
    padding: 8,
  },
  preflightPassBox: {
    borderColor: "#86efac",
    backgroundColor: "#f0fdf4",
  },
  preflightWarningBox: {
    borderColor: "#fbbf24",
    backgroundColor: "#fffbeb",
  },
  preflightBlockedBox: {
    borderColor: "#fca5a5",
    backgroundColor: "#fef2f2",
  },
  preflightText: {
    fontSize: 12,
  },
  preflightPassText: {
    color: "#166534",
  },
  preflightWarningText: {
    color: "#92400e",
  },
  preflightBlockedText: {
    color: "#991b1b",
  },
  releaseIdentityBox: {
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#ffffff",
    borderRadius: 10,
    padding: 10,
  },
  releaseIdentityText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 4,
  },
  releaseIdentityGoodText: {
    color: "#166534",
    fontWeight: "700",
  },
  releaseIdentityWarningText: {
    color: "#b45309",
    fontWeight: "700",
  },
  sectionTitle: {
    marginTop: 14,
    marginBottom: 8,
    fontSize: 16,
    fontWeight: "600",
    color: "#111827",
  },
  submitButton: {
    marginTop: 16,
    borderRadius: 10,
    backgroundColor: "#0f766e",
    paddingVertical: 12,
    alignItems: "center",
  },
  submitButtonDisabled: {
    opacity: 0.6,
  },
  submitButtonText: {
    color: "#ffffff",
    fontWeight: "600",
  },
  responseBox: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: "#d1d5db",
    backgroundColor: "#ffffff",
    borderRadius: 8,
    padding: 10,
    minHeight: 80,
  },
  responseText: {
    color: "#0f172a",
    fontSize: 12,
  },
  summaryButton: {
    marginTop: 8,
    borderRadius: 10,
    backgroundColor: "#1f4f97",
    paddingVertical: 12,
    alignItems: "center",
  },
  dangerButton: {
    marginTop: 8,
    borderRadius: 10,
    backgroundColor: "#b91c1c",
    paddingVertical: 12,
    alignItems: "center",
  },
  buttonRow: {
    marginTop: 8,
    flexDirection: "row",
    gap: 8,
  },
  buttonGrow: {
    flex: 1,
  },
  summaryErrorText: {
    marginTop: 8,
    color: "#b91c1c",
    fontSize: 12,
  },
  captureStatusText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 4,
  },
  sopChecklistBox: {
    marginTop: 10,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#bfdbfe",
    backgroundColor: "#eff6ff",
    padding: 10,
  },
  sopChecklistTitle: {
    color: "#1e3a8a",
    fontSize: 13,
    fontWeight: "700",
    marginBottom: 6,
  },
  sopChecklistItem: {
    borderRadius: 8,
    paddingVertical: 6,
  },
  sopChecklistItemText: {
    color: "#0f172a",
    fontSize: 12,
    fontWeight: "600",
  },
  sopChecklistHintText: {
    color: "#334155",
    fontSize: 11,
    marginTop: 2,
  },
  sopChecklistStatusText: {
    marginTop: 6,
    fontSize: 12,
    fontWeight: "700",
  },
  sopChecklistReadyText: {
    color: "#166534",
  },
  sopChecklistBlockedText: {
    color: "#92400e",
  },
  cameraPreviewWrap: {
    marginTop: 8,
    marginBottom: 8,
    borderRadius: 10,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#cbd5e1",
    backgroundColor: "#0f172a",
  },
  cameraPreview: {
    width: "100%",
    height: 180,
  },
  curveBox: {
    marginTop: 8,
    borderWidth: 1,
    borderColor: "#d1d5db",
    backgroundColor: "#ffffff",
    borderRadius: 8,
    padding: 10,
  },
  curveRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
  },
  curveTimeText: {
    width: 42,
    color: "#334155",
    fontSize: 11,
  },
  curveBarTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#e2e8f0",
    overflow: "hidden",
    marginHorizontal: 8,
  },
  curveBarFill: {
    height: 8,
    borderRadius: 4,
    backgroundColor: "#0f766e",
  },
  curveValueText: {
    width: 44,
    textAlign: "right",
    color: "#0f172a",
    fontSize: 11,
  },
  pendingRow: {
    marginTop: 8,
    marginBottom: 4,
  },
  pendingText: {
    color: "#0f172a",
    fontSize: 13,
    fontWeight: "500",
  },
  pendingItemText: {
    color: "#334155",
    fontSize: 12,
    marginTop: 2,
  },
  syncStatusText: {
    marginTop: 8,
    color: "#0f172a",
    fontSize: 12,
  },
  summaryText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 6,
  },
  summaryMetricText: {
    color: "#0f172a",
    fontSize: 12,
    marginBottom: 4,
  },
  coverageGoodText: {
    color: "#166534",
    fontWeight: "700",
  },
  coverageBadText: {
    color: "#b91c1c",
    fontWeight: "700",
  },
});
