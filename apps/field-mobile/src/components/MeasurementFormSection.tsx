import React from "react";
import { Pressable, Text, View } from "react-native";

import type { QualityStatus } from "../types";
import { styles } from "../styles/appStyles";
import { LabeledInput } from "./LabeledInput";

type MeasurementFormSectionProps = {
  appFlowTime: string;
  appModelId: string;
  appQavg: string;
  appQmax: string;
  appQualityScore: string;
  appQualityStatus: QualityStatus;
  qualitySubmissionWarning: string | null;
  appTqmax: string;
  appVersion: string;
  appVvoid: string;
  attemptNumber: string;
  captureMode: string;
  deviceModel: string;
  measuredAt: string;
  notes: string;
  operatorId: string;
  platform: string;
  refDeviceModel: string;
  refDeviceSerial: string;
  refFlowTime: string;
  refQavg: string;
  refQmax: string;
  refTqmax: string;
  refVvoid: string;
  sessionId: string;
  siteId: string;
  subjectId: string;
  submitting: boolean;
  syncId: string;
  onAppFlowTimeChange: (value: string) => void;
  onAppModelIdChange: (value: string) => void;
  onAppQavgChange: (value: string) => void;
  onAppQmaxChange: (value: string) => void;
  onAppQualityScoreChange: (value: string) => void;
  onAppQualityStatusChange: (value: QualityStatus) => void;
  onAppTqmaxChange: (value: string) => void;
  onAppVersionChange: (value: string) => void;
  onAppVvoidChange: (value: string) => void;
  onAttemptNumberChange: (value: string) => void;
  onCaptureModeChange: (value: string) => void;
  onDeviceModelChange: (value: string) => void;
  onMeasuredAtChange: (value: string) => void;
  onNotesChange: (value: string) => void;
  onOperatorIdChange: (value: string) => void;
  onPlatformChange: (value: string) => void;
  onRefDeviceModelChange: (value: string) => void;
  onRefDeviceSerialChange: (value: string) => void;
  onRefFlowTimeChange: (value: string) => void;
  onRefQavgChange: (value: string) => void;
  onRefQmaxChange: (value: string) => void;
  onRefTqmaxChange: (value: string) => void;
  onRefVvoidChange: (value: string) => void;
  onSessionIdChange: (value: string) => void;
  onSiteIdChange: (value: string) => void;
  onSubjectIdChange: (value: string) => void;
  onSubmit: () => Promise<void>;
  onSyncIdChange: (value: string) => void;
};

export function MeasurementFormSection({
  appFlowTime,
  appModelId,
  appQavg,
  appQmax,
  appQualityScore,
  appQualityStatus,
  qualitySubmissionWarning,
  appTqmax,
  appVersion,
  appVvoid,
  attemptNumber,
  captureMode,
  deviceModel,
  measuredAt,
  notes,
  operatorId,
  platform,
  refDeviceModel,
  refDeviceSerial,
  refFlowTime,
  refQavg,
  refQmax,
  refTqmax,
  refVvoid,
  sessionId,
  siteId,
  subjectId,
  submitting,
  syncId,
  onAppFlowTimeChange,
  onAppModelIdChange,
  onAppQavgChange,
  onAppQmaxChange,
  onAppQualityScoreChange,
  onAppQualityStatusChange,
  onAppTqmaxChange,
  onAppVersionChange,
  onAppVvoidChange,
  onAttemptNumberChange,
  onCaptureModeChange,
  onDeviceModelChange,
  onMeasuredAtChange,
  onNotesChange,
  onOperatorIdChange,
  onPlatformChange,
  onRefDeviceModelChange,
  onRefDeviceSerialChange,
  onRefFlowTimeChange,
  onRefQavgChange,
  onRefQmaxChange,
  onRefTqmaxChange,
  onRefVvoidChange,
  onSessionIdChange,
  onSiteIdChange,
  onSubjectIdChange,
  onSubmit,
  onSyncIdChange,
}: MeasurementFormSectionProps) {
  return (
    <>
      <Text style={styles.sectionTitle}>Session</Text>
      <LabeledInput label="Session ID" value={sessionId} onChangeText={onSessionIdChange} />
      <LabeledInput label="Sync ID" value={syncId} onChangeText={onSyncIdChange} />
      <LabeledInput label="Site ID" value={siteId} onChangeText={onSiteIdChange} />
      <LabeledInput label="Subject ID" value={subjectId} onChangeText={onSubjectIdChange} />
      <LabeledInput label="Operator ID" value={operatorId} onChangeText={onOperatorIdChange} />
      <LabeledInput
        label="Attempt Number"
        value={attemptNumber}
        onChangeText={onAttemptNumberChange}
        keyboardType="number-pad"
      />
      <LabeledInput label="Measured At (ISO)" value={measuredAt} onChangeText={onMeasuredAtChange} />
      <LabeledInput label="Platform (ios/android)" value={platform} onChangeText={onPlatformChange} />
      <LabeledInput label="Device Model" value={deviceModel} onChangeText={onDeviceModelChange} />
      <LabeledInput label="App Version" value={appVersion} onChangeText={onAppVersionChange} />
      <LabeledInput label="Capture Mode" value={captureMode} onChangeText={onCaptureModeChange} />

      <Text style={styles.sectionTitle}>App Measurement</Text>
      <LabeledInput
        label="Qmax (ml/s)"
        value={appQmax}
        onChangeText={onAppQmaxChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Qavg (ml/s)"
        value={appQavg}
        onChangeText={onAppQavgChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Vvoid (ml)"
        value={appVvoid}
        onChangeText={onAppVvoidChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Flow Time (s)"
        value={appFlowTime}
        onChangeText={onAppFlowTimeChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="TQmax (s)"
        value={appTqmax}
        onChangeText={onAppTqmaxChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Quality Status"
        value={appQualityStatus}
        onChangeText={(value) => onAppQualityStatusChange((value as QualityStatus) || "valid")}
      />
      <LabeledInput
        label="Quality Score (0-100)"
        value={appQualityScore}
        onChangeText={onAppQualityScoreChange}
        keyboardType="decimal-pad"
      />
      {qualitySubmissionWarning ? (
        <View style={styles.qualityWarningBox}>
          <Text selectable style={styles.qualityWarningText}>
            {qualitySubmissionWarning}
          </Text>
        </View>
      ) : null}
      <LabeledInput label="Model ID" value={appModelId} onChangeText={onAppModelIdChange} />

      <Text style={styles.sectionTitle}>Reference Uroflowmeter</Text>
      <LabeledInput
        label="Qmax (ml/s)"
        value={refQmax}
        onChangeText={onRefQmaxChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Qavg (ml/s)"
        value={refQavg}
        onChangeText={onRefQavgChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Vvoid (ml)"
        value={refVvoid}
        onChangeText={onRefVvoidChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Flow Time (s)"
        value={refFlowTime}
        onChangeText={onRefFlowTimeChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="TQmax (s)"
        value={refTqmax}
        onChangeText={onRefTqmaxChange}
        keyboardType="decimal-pad"
      />
      <LabeledInput
        label="Reference Device Model"
        value={refDeviceModel}
        onChangeText={onRefDeviceModelChange}
      />
      <LabeledInput
        label="Reference Device Serial"
        value={refDeviceSerial}
        onChangeText={onRefDeviceSerialChange}
      />

      <Text style={styles.sectionTitle}>Notes</Text>
      <LabeledInput label="Notes" value={notes} onChangeText={onNotesChange} multiline />

      <Pressable
        style={[styles.submitButton, submitting && styles.submitButtonDisabled]}
        onPress={() => void onSubmit()}
        disabled={submitting}
      >
        <Text style={styles.submitButtonText}>
          {submitting ? "Submitting..." : "Submit Paired Measurement"}
        </Text>
      </Pressable>
    </>
  );
}
