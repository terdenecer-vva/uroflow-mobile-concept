import React from "react";
import { Pressable, Text, View } from "react-native";
import { CameraView } from "expo-camera";

import type { RuntimeFlowPoint } from "../capture/runtimeCaptureSession";
import { styles } from "../styles/appStyles";
import type {
  OperatorSopChecklistItem,
  OperatorSopChecklistKey,
  OperatorSopChecklistState,
} from "../utils/operatorSopChecklist";
import { RuntimeCurvePreview } from "./RuntimeCurvePreview";

type RuntimeCaptureSectionProps = {
  cameraPermissionGranted: boolean;
  cameraPreviewReady: boolean;
  cameraPreviewRef: React.RefObject<CameraView | null>;
  captureAvgMotionNorm: number;
  captureAlignmentDriftWarning: boolean;
  captureHighMotionRatio: number;
  captureLowConfidenceRatio: number;
  captureRoiValidRatio: number;
  captureRunning: boolean;
  captureSampleCount: number;
  captureStatus: string;
  captureTimingGapWarning: boolean;
  flowSeries: RuntimeFlowPoint[];
  manualAppMetricsOverride: boolean;
  operatorSopChecklistItems: OperatorSopChecklistItem[];
  operatorSopChecklist: OperatorSopChecklistState;
  operatorSopReadinessMessage: string;
  operatorSopReady: boolean;
  roiFrameCount: number;
  roiFrameValid: boolean;
  roiLocked: boolean;
  roiMotionProxy: number;
  roiTextureProxy: number;
  runtimeCaptureContractReady: boolean;
  onCameraMountError: () => void;
  onCameraReady: () => void;
  onRequestCameraPermission: () => Promise<unknown>;
  onStartRuntimeCapture: () => Promise<void>;
  onStopRuntimeCapture: () => Promise<void>;
  onToggleOperatorSopChecklistItem: (key: OperatorSopChecklistKey) => void;
  onToggleManualAppMetricsOverride: () => void;
  onToggleRoiLock: () => void;
};

export function RuntimeCaptureSection({
  cameraPermissionGranted,
  cameraPreviewReady,
  cameraPreviewRef,
  captureAvgMotionNorm,
  captureAlignmentDriftWarning,
  captureHighMotionRatio,
  captureLowConfidenceRatio,
  captureRoiValidRatio,
  captureRunning,
  captureSampleCount,
  captureStatus,
  captureTimingGapWarning,
  flowSeries,
  manualAppMetricsOverride,
  operatorSopChecklistItems,
  operatorSopChecklist,
  operatorSopReadinessMessage,
  operatorSopReady,
  roiFrameCount,
  roiFrameValid,
  roiLocked,
  roiMotionProxy,
  roiTextureProxy,
  runtimeCaptureContractReady,
  onCameraMountError,
  onCameraReady,
  onRequestCameraPermission,
  onStartRuntimeCapture,
  onStopRuntimeCapture,
  onToggleOperatorSopChecklistItem,
  onToggleManualAppMetricsOverride,
  onToggleRoiLock,
}: RuntimeCaptureSectionProps) {
  return (
    <>
      <Text style={styles.sectionTitle}>Runtime Capture (Audio + IMU + Camera Permission)</Text>
      <Text style={styles.captureStatusText}>{captureStatus}</Text>
      <Text style={styles.captureStatusText}>
        Camera permission: {cameraPermissionGranted ? "granted" : "not granted"}, preview:{" "}
        {cameraPreviewReady ? "ready" : "not ready"}, ROI lock: {roiLocked ? "on" : "off"}
      </Text>
      <Text style={styles.captureStatusText}>
        Samples: {captureSampleCount}, avg motion norm: {captureAvgMotionNorm.toFixed(3)}
      </Text>
      <Text style={styles.captureStatusText}>
        quality flags: roi_valid_ratio={captureRoiValidRatio.toFixed(3)}, low_confidence_ratio=
        {captureLowConfidenceRatio.toFixed(3)}, high_motion_ratio=
        {captureHighMotionRatio.toFixed(3)}, timing_gap_warning=
        {captureTimingGapWarning ? "yes" : "no"}, alignment_drift_warning=
        {captureAlignmentDriftWarning ? "yes" : "no"}
      </Text>
      <Text style={styles.captureStatusText}>
        Contract payload:{" "}
        {runtimeCaptureContractReady ? "ready" : "not ready (scaffold fallback)"}
      </Text>
      {!cameraPermissionGranted ? (
        <Pressable style={styles.summaryButton} onPress={() => void onRequestCameraPermission()}>
          <Text style={styles.submitButtonText}>Grant Camera Permission</Text>
        </Pressable>
      ) : (
        <View style={styles.cameraPreviewWrap}>
          <CameraView
            ref={cameraPreviewRef}
            style={styles.cameraPreview}
            facing="back"
            onCameraReady={onCameraReady}
            onMountError={onCameraMountError}
          />
        </View>
      )}
      <Pressable
        style={[styles.summaryButton, !cameraPermissionGranted && styles.submitButtonDisabled]}
        onPress={onToggleRoiLock}
        disabled={!cameraPermissionGranted}
      >
        <Text style={styles.submitButtonText}>{roiLocked ? "Unlock ROI" : "Lock ROI"}</Text>
      </Pressable>
      <Text style={styles.captureStatusText}>
        ROI frames: {roiFrameCount}, valid: {roiFrameValid ? "yes" : "no"}, motion proxy:{" "}
        {roiMotionProxy.toFixed(3)}, texture proxy: {roiTextureProxy.toFixed(3)}
      </Text>
      <Pressable style={styles.summaryButton} onPress={onToggleManualAppMetricsOverride}>
        <Text style={styles.submitButtonText}>
          App metrics mode: {manualAppMetricsOverride ? "manual" : "runtime auto-fill"}
        </Text>
      </Pressable>
      <View style={styles.sopChecklistBox}>
        <Text style={styles.sopChecklistTitle}>Operator SOP checklist</Text>
        {operatorSopChecklistItems.map((item) => (
          <Pressable
            key={item.key}
            style={styles.sopChecklistItem}
            onPress={() => onToggleOperatorSopChecklistItem(item.key)}
          >
            <Text style={styles.sopChecklistItemText}>
              {operatorSopChecklist[item.key] ? "[x]" : "[ ]"} {item.label}
            </Text>
            <Text style={styles.sopChecklistHintText}>{item.evidenceHint}</Text>
          </Pressable>
        ))}
        <Text
          style={[
            styles.sopChecklistStatusText,
            operatorSopReady
              ? styles.sopChecklistReadyText
              : styles.sopChecklistBlockedText,
          ]}
        >
          {operatorSopReadinessMessage}
        </Text>
      </View>
      <View style={styles.buttonRow}>
        <Pressable
          style={[
            styles.summaryButton,
            styles.buttonGrow,
            captureRunning && styles.submitButtonDisabled,
          ]}
          onPress={() => void onStartRuntimeCapture()}
          disabled={captureRunning}
        >
          <Text style={styles.submitButtonText}>
            {captureRunning ? "Capture running..." : "Start Capture"}
          </Text>
        </Pressable>
        <Pressable
          style={[
            styles.dangerButton,
            styles.buttonGrow,
            !captureRunning && styles.submitButtonDisabled,
          ]}
          onPress={() => void onStopRuntimeCapture()}
          disabled={!captureRunning}
        >
          <Text style={styles.submitButtonText}>Stop Capture</Text>
        </Pressable>
      </View>

      <Text style={styles.sectionTitle}>Runtime Q(t) Preview</Text>
      <RuntimeCurvePreview flowSeries={flowSeries} />
    </>
  );
}
