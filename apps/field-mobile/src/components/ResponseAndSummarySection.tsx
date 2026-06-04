import React from "react";
import { Pressable, Text, View } from "react-native";

import type {
  CaptureCoverageSummaryResponse,
  ComparisonSummaryResponse,
  SummaryQualityStatus,
} from "../types";
import { COVERAGE_GOAL_RATIO, formatNullable } from "../utils/appHelpers";
import { styles } from "../styles/appStyles";
import { LabeledInput } from "./LabeledInput";

type ResponseAndSummarySectionProps = {
  coverageError: string;
  coverageLoading: boolean;
  coverageSummary: CaptureCoverageSummaryResponse | null;
  lastResponse: string;
  summary: ComparisonSummaryResponse | null;
  summaryError: string;
  summaryLoading: boolean;
  summaryQualityStatus: SummaryQualityStatus;
  summarySyncId: string;
  onLoadBothSummaries: () => Promise<void>;
  onLoadCaptureCoverageSummary: () => Promise<void>;
  onLoadComparisonSummary: () => Promise<void>;
  onSummaryQualityStatusChange: (value: SummaryQualityStatus) => void;
  onSummarySyncIdChange: (value: string) => void;
};

export function ResponseAndSummarySection({
  coverageError,
  coverageLoading,
  coverageSummary,
  lastResponse,
  summary,
  summaryError,
  summaryLoading,
  summaryQualityStatus,
  summarySyncId,
  onLoadBothSummaries,
  onLoadCaptureCoverageSummary,
  onLoadComparisonSummary,
  onSummaryQualityStatusChange,
  onSummarySyncIdChange,
}: ResponseAndSummarySectionProps) {
  return (
    <>
      <Text style={styles.sectionTitle}>Last API Response</Text>
      <View style={styles.responseBox}>
        <Text style={styles.responseText}>{lastResponse || "No response yet"}</Text>
      </View>

      <Text style={styles.sectionTitle}>Comparison Summary (App vs Reference)</Text>
      <Text style={styles.helperText}>
        Uses current filters: site_id + optional sync_id + quality status.
      </Text>
      <Pressable
        style={[
          styles.summaryButton,
          (summaryLoading || coverageLoading) && styles.submitButtonDisabled,
        ]}
        onPress={() => void onLoadBothSummaries()}
        disabled={summaryLoading || coverageLoading}
      >
        <Text style={styles.submitButtonText}>
          {summaryLoading || coverageLoading ? "Loading both summaries..." : "Load Both Summaries"}
        </Text>
      </Pressable>
      <LabeledInput
        label="Summary Quality Status (valid/repeat/reject/all)"
        value={summaryQualityStatus}
        onChangeText={(value) =>
          onSummaryQualityStatusChange((value as SummaryQualityStatus) || "valid")
        }
      />
      <LabeledInput
        label="Summary Sync ID (optional)"
        value={summarySyncId}
        onChangeText={onSummarySyncIdChange}
      />
      <Pressable
        style={[styles.summaryButton, summaryLoading && styles.submitButtonDisabled]}
        onPress={() => void onLoadComparisonSummary()}
        disabled={summaryLoading}
      >
        <Text style={styles.submitButtonText}>
          {summaryLoading ? "Loading..." : "Load Comparison Summary"}
        </Text>
      </Pressable>
      {summaryError ? <Text style={styles.summaryErrorText}>{summaryError}</Text> : null}
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

      <Text style={styles.sectionTitle}>Capture Coverage Summary</Text>
      <Pressable
        style={[styles.summaryButton, coverageLoading && styles.submitButtonDisabled]}
        onPress={() => void onLoadCaptureCoverageSummary()}
        disabled={coverageLoading}
      >
        <Text style={styles.submitButtonText}>
          {coverageLoading ? "Loading..." : "Load Coverage Summary"}
        </Text>
      </Pressable>
      {coverageError ? <Text style={styles.summaryErrorText}>{coverageError}</Text> : null}
      <View style={styles.responseBox}>
        {coverageSummary ? (
          <>
            <Text style={styles.summaryText}>
              Paired total: {coverageSummary.paired_total}, with capture:{" "}
              {coverageSummary.paired_with_capture}, without capture:{" "}
              {coverageSummary.paired_without_capture}
            </Text>
            <Text style={styles.summaryText}>
              Coverage ratio:{" "}
              <Text
                style={
                  coverageSummary.coverage_ratio >= COVERAGE_GOAL_RATIO
                    ? styles.coverageGoodText
                    : styles.coverageBadText
                }
              >
                {(coverageSummary.coverage_ratio * 100).toFixed(1)}%
              </Text>{" "}
              (target: {(COVERAGE_GOAL_RATIO * 100).toFixed(0)}%)
            </Text>
            <Text style={styles.summaryText}>
              Match modes: paired_id=
              {coverageSummary.capture_match_distribution.paired_id ?? 0}, session_identity=
              {coverageSummary.capture_match_distribution.session_identity ?? 0}, none=
              {coverageSummary.capture_match_distribution.none ?? 0}
            </Text>
            <Text style={styles.summaryText}>
              Quality: valid={coverageSummary.quality_distribution.valid ?? 0}, repeat=
              {coverageSummary.quality_distribution.repeat ?? 0}, reject=
              {coverageSummary.quality_distribution.reject ?? 0}
            </Text>
          </>
        ) : (
          <Text style={styles.responseText}>No coverage summary loaded yet</Text>
        )}
      </View>
    </>
  );
}
