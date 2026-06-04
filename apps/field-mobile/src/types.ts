export type QualityStatus = "valid" | "repeat" | "reject";
export type SummaryQualityStatus = QualityStatus | "all";

export type ComparisonMetricSummary = {
  metric: string;
  paired_samples: number;
  mean_error: number | null;
  mean_absolute_error: number | null;
  rmse: number | null;
  pearson_r: number | null;
};

export type ComparisonSummaryResponse = {
  records_considered: number;
  records_matched_filters: number;
  quality_distribution: Record<string, number>;
  metrics: ComparisonMetricSummary[];
};

export type CaptureCoverageSummaryResponse = {
  paired_total: number;
  paired_with_capture: number;
  paired_without_capture: number;
  coverage_ratio: number;
  quality_distribution: Record<string, number>;
  capture_match_distribution: Record<string, number>;
};

export type AuthContextResponse = {
  auth_result: string;
  actor_role: string | null;
  actor_site_id: string | null;
  actor_operator_id: string | null;
  cross_site_allowed: boolean;
};

export type PairedPayload = {
  session: {
    session_id: string;
    sync_id: string | null;
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

export type CapturePackagePayload = {
  session: PairedPayload["session"];
  package_type: "capture_contract_json";
  capture_payload: Record<string, unknown>;
  paired_measurement_id: number | null;
  notes: string | null;
};

export type EndpointPayload = PairedPayload | CapturePackagePayload;

export type PendingEndpoint = "paired_measurements" | "capture_packages";

export type PendingSubmission = {
  id: string;
  created_at: string;
  endpoint: PendingEndpoint;
  payload: EndpointPayload;
  request_headers: RequestHeaderContext;
  attempt_count: number;
  last_attempt_at: string | null;
  last_error: string | null;
  last_status_code: number | null;
};

export type AppSettings = {
  api_base_url: string;
  api_key: string;
  actor_role: string;
  site_id: string;
  operator_id: string;
  summary_quality_status: SummaryQualityStatus;
  summary_sync_id: string;
  request_timeout_ms: string;
};

export type SubmitAttemptResult = {
  ok: boolean;
  statusCode: number | null;
  body: string;
  retryable: boolean;
};

export type RequestHeaderContext = {
  api_key: string;
  actor_role: string;
  site_id: string;
  operator_id: string;
  request_id?: string;
};

export type RoiFrameAnalysisState = {
  prevHash: number | null;
  prevLength: number | null;
};
