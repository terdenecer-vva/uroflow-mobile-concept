import React, { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import AsyncStorage from "@react-native-async-storage/async-storage";

type QualityStatus = "valid" | "repeat" | "reject";
type SummaryQualityStatus = QualityStatus | "all";

type ComparisonMetricSummary = {
  metric: string;
  paired_samples: number;
  mean_error: number | null;
  mean_absolute_error: number | null;
  rmse: number | null;
  pearson_r: number | null;
};

type ComparisonSummaryResponse = {
  records_considered: number;
  records_matched_filters: number;
  quality_distribution: Record<string, number>;
  metrics: ComparisonMetricSummary[];
};

type PairedPayload = {
  session: {
    session_id: string;
    site_id: string;
    subject_id: string;
    operator_id: string;
    attempt_number: number | null;
    measured_at: string;
    platform: string;
    device_model: string | null;
    app_version: string | null;
    capture_mode: string;
  };
  app: {
    metrics: {
      qmax_ml_s: number | null;
      qavg_ml_s: number | null;
      vvoid_ml: number | null;
      flow_time_s: number | null;
      tqmax_s: number | null;
    };
    quality_status: QualityStatus;
    quality_score: number | null;
    model_id: string | null;
  };
  reference: {
    metrics: {
      qmax_ml_s: number | null;
      qavg_ml_s: number | null;
      vvoid_ml: number | null;
      flow_time_s: number | null;
      tqmax_s: number | null;
    };
    device_model: string | null;
    device_serial: string | null;
  };
  notes: string | null;
};

type PendingSubmission = {
  id: string;
  created_at: string;
  payload: PairedPayload;
};

const PENDING_SUBMISSIONS_KEY = "uroflow_pending_submissions_v1";

const defaultMeasuredAt = new Date().toISOString().slice(0, 19) + "Z";

function parseNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) {
    return null;
  }
  return parsed;
}

function createSessionId(): string {
  const now = new Date();
  const y = now.getUTCFullYear();
  const m = String(now.getUTCMonth() + 1).padStart(2, "0");
  const d = String(now.getUTCDate()).padStart(2, "0");
  const h = String(now.getUTCHours()).padStart(2, "0");
  const min = String(now.getUTCMinutes()).padStart(2, "0");
  const s = String(now.getUTCSeconds()).padStart(2, "0");
  return `SESSION-${y}${m}${d}-${h}${min}${s}`;
}

function formatNullable(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(3);
}

function createPendingId(): string {
  const randomPart = Math.random().toString(36).slice(2, 10);
  return `PENDING-${Date.now()}-${randomPart}`;
}

async function loadPendingSubmissions(): Promise<PendingSubmission[]> {
  const raw = await AsyncStorage.getItem(PENDING_SUBMISSIONS_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed as PendingSubmission[];
  } catch {
    return [];
  }
}

async function savePendingSubmissions(queue: PendingSubmission[]): Promise<void> {
  await AsyncStorage.setItem(PENDING_SUBMISSIONS_KEY, JSON.stringify(queue));
}

export default function App() {
  const defaultPlatform = Platform.OS === "ios" ? "ios" : "android";

  const [apiBaseUrl, setApiBaseUrl] = useState("http://127.0.0.1:8000");
  const [apiKey, setApiKey] = useState("");
  const [actorRole, setActorRole] = useState("operator");
  const [sessionId, setSessionId] = useState(createSessionId());
  const [siteId, setSiteId] = useState("SITE-001");
  const [subjectId, setSubjectId] = useState("SUBJ-001");
  const [operatorId, setOperatorId] = useState("OP-01");
  const [attemptNumber, setAttemptNumber] = useState("1");
  const [measuredAt, setMeasuredAt] = useState(defaultMeasuredAt);
  const [platform, setPlatform] = useState(defaultPlatform);
  const [deviceModel, setDeviceModel] = useState(Platform.OS);
  const [appVersion, setAppVersion] = useState("0.1.0");
  const [captureMode, setCaptureMode] = useState("water_impact");

  const [appQmax, setAppQmax] = useState("");
  const [appQavg, setAppQavg] = useState("");
  const [appVvoid, setAppVvoid] = useState("");
  const [appFlowTime, setAppFlowTime] = useState("");
  const [appTqmax, setAppTqmax] = useState("");
  const [appQualityStatus, setAppQualityStatus] = useState<QualityStatus>("valid");
  const [appQualityScore, setAppQualityScore] = useState("");
  const [appModelId, setAppModelId] = useState("fusion-v0.1");

  const [refQmax, setRefQmax] = useState("");
  const [refQavg, setRefQavg] = useState("");
  const [refVvoid, setRefVvoid] = useState("");
  const [refFlowTime, setRefFlowTime] = useState("");
  const [refTqmax, setRefTqmax] = useState("");
  const [refDeviceModel, setRefDeviceModel] = useState("");
  const [refDeviceSerial, setRefDeviceSerial] = useState("");

  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastResponse, setLastResponse] = useState<string>("");
  const [pendingCount, setPendingCount] = useState(0);
  const [syncingPending, setSyncingPending] = useState(false);
  const [summaryQualityStatus, setSummaryQualityStatus] = useState<SummaryQualityStatus>("valid");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");
  const [summary, setSummary] = useState<ComparisonSummaryResponse | null>(null);

  const payload = useMemo<PairedPayload>(() => {
    return {
      session: {
        session_id: sessionId.trim(),
        site_id: siteId.trim(),
        subject_id: subjectId.trim(),
        operator_id: operatorId.trim(),
        attempt_number: parseNumber(attemptNumber),
        measured_at: measuredAt.trim(),
        platform,
        device_model: deviceModel.trim() || null,
        app_version: appVersion.trim() || null,
        capture_mode: captureMode,
      },
      app: {
        metrics: {
          qmax_ml_s: parseNumber(appQmax),
          qavg_ml_s: parseNumber(appQavg),
          vvoid_ml: parseNumber(appVvoid),
          flow_time_s: parseNumber(appFlowTime),
          tqmax_s: parseNumber(appTqmax),
        },
        quality_status: appQualityStatus,
        quality_score: parseNumber(appQualityScore),
        model_id: appModelId.trim() || null,
      },
      reference: {
        metrics: {
          qmax_ml_s: parseNumber(refQmax),
          qavg_ml_s: parseNumber(refQavg),
          vvoid_ml: parseNumber(refVvoid),
          flow_time_s: parseNumber(refFlowTime),
          tqmax_s: parseNumber(refTqmax),
        },
        device_model: refDeviceModel.trim() || null,
        device_serial: refDeviceSerial.trim() || null,
      },
      notes: notes.trim() || null,
    };
  }, [
    appFlowTime,
    appModelId,
    appQavg,
    appQmax,
    appQualityScore,
    appQualityStatus,
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
  ]);

  useEffect(() => {
    void (async () => {
      const queue = await loadPendingSubmissions();
      setPendingCount(queue.length);
    })();
  }, []);

  async function enqueuePendingSubmission(item: PendingSubmission): Promise<void> {
    const queue = await loadPendingSubmissions();
    queue.push(item);
    await savePendingSubmissions(queue);
    setPendingCount(queue.length);
  }

  async function attemptSubmit(currentPayload: PairedPayload): Promise<{
    ok: boolean;
    statusCode: number | null;
    body: string;
  }> {
    const url = `${apiBaseUrl.replace(/\/$/, "")}/api/v1/paired-measurements`;
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (apiKey.trim()) {
        headers["x-api-key"] = apiKey.trim();
      }
      if (operatorId.trim()) {
        headers["x-operator-id"] = operatorId.trim();
      }
      if (siteId.trim()) {
        headers["x-site-id"] = siteId.trim();
      }
      if (actorRole.trim()) {
        headers["x-actor-role"] = actorRole.trim();
      }
      headers["x-request-id"] = createPendingId();

      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(currentPayload),
      });
      const body = await response.text();
      return {
        ok: response.ok,
        statusCode: response.status,
        body,
      };
    } catch (error) {
      return {
        ok: false,
        statusCode: null,
        body: String(error),
      };
    }
  }

  async function syncPendingSubmissions(): Promise<void> {
    setSyncingPending(true);
    setSummaryError("");
    try {
      const queue = await loadPendingSubmissions();
      if (queue.length === 0) {
        setPendingCount(0);
        return;
      }

      const remaining: PendingSubmission[] = [];
      let synced = 0;

      for (const item of queue) {
        const result = await attemptSubmit(item.payload);
        if (result.ok) {
          synced += 1;
        } else {
          remaining.push(item);
        }
      }

      await savePendingSubmissions(remaining);
      setPendingCount(remaining.length);

      if (synced > 0) {
        Alert.alert("Sync completed", `Synced: ${synced}, remaining: ${remaining.length}`);
      }
      if (synced === 0 && remaining.length > 0) {
        setLastResponse("Pending queue was not synced. Check API URL and API key.");
      }
    } finally {
      setSyncingPending(false);
    }
  }

  function validateRequired(): string | null {
    if (!payload.session.session_id) {
      return "session_id is required";
    }
    if (!payload.session.site_id || !payload.session.subject_id || !payload.session.operator_id) {
      return "site_id, subject_id, operator_id are required";
    }
    if (!payload.session.attempt_number || payload.session.attempt_number < 1) {
      return "attempt_number must be >= 1";
    }
    if (!payload.session.measured_at) {
      return "measured_at is required";
    }
    if (payload.app.metrics.qmax_ml_s == null || payload.app.metrics.qavg_ml_s == null || payload.app.metrics.vvoid_ml == null) {
      return "App metrics qmax/qavg/vvoid are required";
    }
    if (payload.reference.metrics.qmax_ml_s == null || payload.reference.metrics.qavg_ml_s == null || payload.reference.metrics.vvoid_ml == null) {
      return "Reference metrics qmax/qavg/vvoid are required";
    }
    return null;
  }

  async function submitPayload() {
    const validationError = validateRequired();
    if (validationError) {
      Alert.alert("Validation", validationError);
      return;
    }

    setSubmitting(true);
    setLastResponse("");

    try {
      const result = await attemptSubmit(payload);
      if (result.ok) {
        setLastResponse(result.body);
        Alert.alert("Submitted", "Paired measurement uploaded");
        setSessionId(createSessionId());
        return;
      }

      const pendingItem: PendingSubmission = {
        id: createPendingId(),
        created_at: new Date().toISOString(),
        payload,
      };
      await enqueuePendingSubmission(pendingItem);
      setLastResponse(
        `Queued for retry. Last error: ${
          result.statusCode ? `HTTP ${result.statusCode}` : "NETWORK"
        } ${result.body}`
      );
      Alert.alert(
        "Saved offline",
        "No successful upload now. Record added to pending queue.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function loadComparisonSummary() {
    const baseUrl = apiBaseUrl.replace(/\/$/, "");
    const params = new URLSearchParams();
    if (siteId.trim()) {
      params.set("site_id", siteId.trim());
    }
    params.set("quality_status", summaryQualityStatus);
    const url = `${baseUrl}/api/v1/comparison-summary?${params.toString()}`;

    setSummaryLoading(true);
    setSummaryError("");

    try {
      const headers: Record<string, string> = {};
      if (apiKey.trim()) {
        headers["x-api-key"] = apiKey.trim();
      }
      if (operatorId.trim()) {
        headers["x-operator-id"] = operatorId.trim();
      }
      if (siteId.trim()) {
        headers["x-site-id"] = siteId.trim();
      }
      if (actorRole.trim()) {
        headers["x-actor-role"] = actorRole.trim();
      }
      headers["x-request-id"] = createPendingId();
      const response = await fetch(url, { headers });
      const body = await response.text();
      if (!response.ok) {
        setSummary(null);
        setSummaryError(`HTTP ${response.status}: ${body}`);
        return;
      }
      setSummary(JSON.parse(body) as ComparisonSummaryResponse);
    } catch (error) {
      setSummary(null);
      setSummaryError(String(error));
    } finally {
      setSummaryLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.title}>Uroflow Field Capture</Text>
        <Text style={styles.subtitle}>Pair app result with reference uroflowmeter</Text>

        <Text style={styles.sectionTitle}>API</Text>
        <LabeledInput label="API Base URL" value={apiBaseUrl} onChangeText={setApiBaseUrl} />
        <LabeledInput label="API Key (x-api-key)" value={apiKey} onChangeText={setApiKey} />
        <LabeledInput label="Actor Role (x-actor-role)" value={actorRole} onChangeText={setActorRole} />
        <View style={styles.pendingRow}>
          <Text style={styles.pendingText}>Pending submissions: {pendingCount}</Text>
        </View>
        <Pressable
          style={[styles.summaryButton, syncingPending && styles.submitButtonDisabled]}
          onPress={() => void syncPendingSubmissions()}
          disabled={syncingPending}
        >
          <Text style={styles.submitButtonText}>
            {syncingPending ? "Syncing..." : "Sync Pending Queue"}
          </Text>
        </Pressable>

        <Text style={styles.sectionTitle}>Session</Text>
        <LabeledInput label="Session ID" value={sessionId} onChangeText={setSessionId} />
        <LabeledInput label="Site ID" value={siteId} onChangeText={setSiteId} />
        <LabeledInput label="Subject ID" value={subjectId} onChangeText={setSubjectId} />
        <LabeledInput label="Operator ID" value={operatorId} onChangeText={setOperatorId} />
        <LabeledInput label="Attempt Number" value={attemptNumber} onChangeText={setAttemptNumber} keyboardType="number-pad" />
        <LabeledInput label="Measured At (ISO)" value={measuredAt} onChangeText={setMeasuredAt} />
        <LabeledInput label="Platform (ios/android)" value={platform} onChangeText={setPlatform} />
        <LabeledInput label="Device Model" value={deviceModel} onChangeText={setDeviceModel} />
        <LabeledInput label="App Version" value={appVersion} onChangeText={setAppVersion} />
        <LabeledInput label="Capture Mode" value={captureMode} onChangeText={setCaptureMode} />

        <Text style={styles.sectionTitle}>App Measurement</Text>
        <LabeledInput label="Qmax (ml/s)" value={appQmax} onChangeText={setAppQmax} keyboardType="decimal-pad" />
        <LabeledInput label="Qavg (ml/s)" value={appQavg} onChangeText={setAppQavg} keyboardType="decimal-pad" />
        <LabeledInput label="Vvoid (ml)" value={appVvoid} onChangeText={setAppVvoid} keyboardType="decimal-pad" />
        <LabeledInput label="Flow Time (s)" value={appFlowTime} onChangeText={setAppFlowTime} keyboardType="decimal-pad" />
        <LabeledInput label="TQmax (s)" value={appTqmax} onChangeText={setAppTqmax} keyboardType="decimal-pad" />
        <LabeledInput label="Quality Status" value={appQualityStatus} onChangeText={(value) => setAppQualityStatus((value as QualityStatus) || "valid")} />
        <LabeledInput label="Quality Score (0-100)" value={appQualityScore} onChangeText={setAppQualityScore} keyboardType="decimal-pad" />
        <LabeledInput label="Model ID" value={appModelId} onChangeText={setAppModelId} />

        <Text style={styles.sectionTitle}>Reference Uroflowmeter</Text>
        <LabeledInput label="Qmax (ml/s)" value={refQmax} onChangeText={setRefQmax} keyboardType="decimal-pad" />
        <LabeledInput label="Qavg (ml/s)" value={refQavg} onChangeText={setRefQavg} keyboardType="decimal-pad" />
        <LabeledInput label="Vvoid (ml)" value={refVvoid} onChangeText={setRefVvoid} keyboardType="decimal-pad" />
        <LabeledInput label="Flow Time (s)" value={refFlowTime} onChangeText={setRefFlowTime} keyboardType="decimal-pad" />
        <LabeledInput label="TQmax (s)" value={refTqmax} onChangeText={setRefTqmax} keyboardType="decimal-pad" />
        <LabeledInput label="Reference Device Model" value={refDeviceModel} onChangeText={setRefDeviceModel} />
        <LabeledInput label="Reference Device Serial" value={refDeviceSerial} onChangeText={setRefDeviceSerial} />

        <Text style={styles.sectionTitle}>Notes</Text>
        <LabeledInput label="Notes" value={notes} onChangeText={setNotes} multiline />

        <Pressable style={[styles.submitButton, submitting && styles.submitButtonDisabled]} onPress={submitPayload} disabled={submitting}>
          <Text style={styles.submitButtonText}>{submitting ? "Submitting..." : "Submit Paired Measurement"}</Text>
        </Pressable>

        <Text style={styles.sectionTitle}>Last API Response</Text>
        <View style={styles.responseBox}>
          <Text style={styles.responseText}>{lastResponse || "No response yet"}</Text>
        </View>

        <Text style={styles.sectionTitle}>Comparison Summary (App vs Reference)</Text>
        <LabeledInput
          label="Summary Quality Status (valid/repeat/reject/all)"
          value={summaryQualityStatus}
          onChangeText={(value) =>
            setSummaryQualityStatus((value as SummaryQualityStatus) || "valid")
          }
        />
        <Pressable
          style={[styles.summaryButton, summaryLoading && styles.submitButtonDisabled]}
          onPress={loadComparisonSummary}
          disabled={summaryLoading}
        >
          <Text style={styles.submitButtonText}>
            {summaryLoading ? "Loading..." : "Load Comparison Summary"}
          </Text>
        </Pressable>
        {summaryError ? (
          <Text style={styles.summaryErrorText}>{summaryError}</Text>
        ) : null}
        <View style={styles.responseBox}>
          {summary ? (
            <>
              <Text style={styles.summaryText}>
                Records considered: {summary.records_considered} / {summary.records_matched_filters}
              </Text>
              <Text style={styles.summaryText}>
                Quality distribution: valid={summary.quality_distribution.valid ?? 0} repeat=
                {summary.quality_distribution.repeat ?? 0} reject=
                {summary.quality_distribution.reject ?? 0}
              </Text>
              {summary.metrics.map((metric) => (
                <Text key={metric.metric} style={styles.summaryMetricText}>
                  {metric.metric}: n={metric.paired_samples}, MAE=
                  {formatNullable(metric.mean_absolute_error)}, bias=
                  {formatNullable(metric.mean_error)}, RMSE={formatNullable(metric.rmse)}, r=
                  {formatNullable(metric.pearson_r)}
                </Text>
              ))}
            </>
          ) : (
            <Text style={styles.responseText}>No summary loaded yet</Text>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

type InputProps = {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  keyboardType?: "default" | "number-pad" | "decimal-pad";
  multiline?: boolean;
};

function LabeledInput({
  label,
  value,
  onChangeText,
  keyboardType = "default",
  multiline = false,
}: InputProps) {
  return (
    <View style={styles.inputWrap}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && styles.multilineInput]}
        value={value}
        onChangeText={onChangeText}
        keyboardType={keyboardType}
        multiline={multiline}
      />
    </View>
  );
}

const styles = StyleSheet.create({
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
  sectionTitle: {
    marginTop: 14,
    marginBottom: 8,
    fontSize: 16,
    fontWeight: "600",
    color: "#111827",
  },
  inputWrap: {
    marginBottom: 8,
  },
  label: {
    marginBottom: 4,
    fontSize: 13,
    color: "#334155",
  },
  input: {
    borderWidth: 1,
    borderColor: "#cbd5e1",
    borderRadius: 8,
    backgroundColor: "#ffffff",
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
    color: "#111827",
  },
  multilineInput: {
    minHeight: 70,
    textAlignVertical: "top",
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
  summaryErrorText: {
    marginTop: 8,
    color: "#b91c1c",
    fontSize: 12,
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
});
