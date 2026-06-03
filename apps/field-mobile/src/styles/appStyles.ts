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
