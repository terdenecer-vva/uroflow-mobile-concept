export type CaptureContractSample = {
  t_s: number;
  depth_level_mm: number | null;
  rgb_level_mm: number | null;
  depth_confidence: number;
  audio_rms_dbfs: number;
  motion_norm: number;
  roi_valid: boolean;
};

export type CaptureContractQualityStatus = "valid" | "repeat" | "reject";

export type CaptureContractRuntimeFlowPoint = {
  t_s: number;
  flow_ml_s: number;
};

export type CaptureContractAnalysis = {
  runtime_flow_series?: CaptureContractRuntimeFlowPoint[];
  runtime_quality?: {
    quality_score?: number;
    quality_status?: CaptureContractQualityStatus;
    roi_valid_ratio?: number;
    low_confidence_ratio?: number;
  };
};

export type CaptureContractPayload = {
  schema_version: "ios_capture_v1";
  session: {
    session_id: string;
    sync_id: string | null;
    started_at: string;
    mode: string;
    device: {
      model: string;
      ios_version: string;
    };
    app: {
      version: string;
    };
    calibration: {
      ml_per_mm: number;
      min_depth_confidence: number;
      camera_distance_mm: number;
    };
    privacy: {
      store_raw_video: false;
      store_raw_audio: false;
      roi_only: true;
    };
  };
  samples: CaptureContractSample[];
  analysis?: CaptureContractAnalysis;
};

export type BuildCaptureContractInput = {
  sessionId: string;
  syncId: string | null;
  startedAtIso: string;
  captureMode: string;
  deviceModel: string | null;
  iosVersion: string;
  appVersion: string | null;
  qmaxMlS: number | null;
  qavgMlS: number | null;
  flowTimeS: number | null;
};

export type BuildCaptureContractFromSamplesInput = {
  sessionId: string;
  syncId: string | null;
  startedAtIso: string;
  captureMode: string;
  deviceModel: string | null;
  iosVersion: string;
  appVersion: string | null;
  samples: CaptureContractSample[];
  minDepthConfidence?: number;
  cameraDistanceMm?: number;
  sourceLabel?: string;
  analysis?: CaptureContractAnalysis;
};

const DEFAULT_ML_PER_MM = 8.0;
const DEFAULT_SAMPLE_STEP_S = 0.5;

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value));
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function normalizeStartedAt(startedAtIso: string): string {
  const parsed = new Date(startedAtIso);
  if (Number.isNaN(parsed.getTime())) {
    return new Date().toISOString();
  }
  return parsed.toISOString();
}

function sanitizeRuntimeFlowSeries(
  flowSeries: CaptureContractRuntimeFlowPoint[] | undefined,
): CaptureContractRuntimeFlowPoint[] {
  if (!flowSeries || flowSeries.length === 0) {
    return [];
  }
  const finite = flowSeries
    .filter(
      (point) =>
        Number.isFinite(point.t_s) && Number.isFinite(point.flow_ml_s) && point.t_s >= 0,
    )
    .map((point) => ({ t_s: round4(point.t_s), flow_ml_s: round4(Math.max(0, point.flow_ml_s)) }));
  if (finite.length <= 120) {
    return finite;
  }
  const step = Math.ceil(finite.length / 120);
  const reduced: CaptureContractRuntimeFlowPoint[] = [];
  for (let index = 0; index < finite.length; index += step) {
    reduced.push(finite[index]);
  }
  const lastPoint = finite[finite.length - 1];
  const tailPoint = reduced[reduced.length - 1];
  if (tailPoint.t_s !== lastPoint.t_s || tailPoint.flow_ml_s !== lastPoint.flow_ml_s) {
    reduced.push(lastPoint);
  }
  return reduced;
}

function sanitizeAnalysis(
  analysis: CaptureContractAnalysis | undefined,
): CaptureContractAnalysis | undefined {
  if (!analysis) {
    return undefined;
  }
  const runtimeFlowSeries = sanitizeRuntimeFlowSeries(analysis.runtime_flow_series);
  const runtimeQualityRaw = analysis.runtime_quality;
  const runtimeQuality: CaptureContractAnalysis["runtime_quality"] = {};
  if (runtimeQualityRaw) {
    if (Number.isFinite(runtimeQualityRaw.quality_score)) {
      runtimeQuality.quality_score = round4(Math.max(0, runtimeQualityRaw.quality_score as number));
    }
    if (
      runtimeQualityRaw.quality_status === "valid" ||
      runtimeQualityRaw.quality_status === "repeat" ||
      runtimeQualityRaw.quality_status === "reject"
    ) {
      runtimeQuality.quality_status = runtimeQualityRaw.quality_status;
    }
    if (Number.isFinite(runtimeQualityRaw.roi_valid_ratio)) {
      runtimeQuality.roi_valid_ratio = round4(
        clamp(runtimeQualityRaw.roi_valid_ratio as number, 0, 1),
      );
    }
    if (Number.isFinite(runtimeQualityRaw.low_confidence_ratio)) {
      runtimeQuality.low_confidence_ratio = round4(
        clamp(runtimeQualityRaw.low_confidence_ratio as number, 0, 1),
      );
    }
  }
  const hasRuntimeQuality = Object.keys(runtimeQuality).length > 0;
  if (!hasRuntimeQuality && runtimeFlowSeries.length === 0) {
    return undefined;
  }
  return {
    ...(runtimeFlowSeries.length > 0 ? { runtime_flow_series: runtimeFlowSeries } : {}),
    ...(hasRuntimeQuality ? { runtime_quality: runtimeQuality } : {}),
  };
}

function createSamples(input: BuildCaptureContractInput): CaptureContractSample[] {
  const qmax = input.qmaxMlS ?? 0;
  const qavg = input.qavgMlS ?? 0;
  const flowTime = clamp(input.flowTimeS ?? 10, 3, 60);

  const stepS = DEFAULT_SAMPLE_STEP_S;
  const sampleCount = Math.max(8, Math.floor(flowTime / stepS) + 1);
  const inferredPeak = Math.max(6, qmax, qavg > 0 ? qavg * 1.35 : 0);

  let cumulativeVolumeMl = 0;
  const samples: CaptureContractSample[] = [];

  for (let index = 0; index < sampleCount; index += 1) {
    const progress = sampleCount > 1 ? index / (sampleCount - 1) : 0;
    const bell = Math.sin(Math.PI * progress);
    const flow = Math.max(0, inferredPeak * bell);

    cumulativeVolumeMl += flow * stepS;
    const depthLevel = cumulativeVolumeMl / DEFAULT_ML_PER_MM;

    const confidence = progress > 0.65 && progress < 0.75 ? 0.55 : 0.92;
    const motion = 0.02 + (index % 3) * 0.01;

    samples.push({
      t_s: round4(index * stepS),
      depth_level_mm: round4(depthLevel),
      rgb_level_mm: round4(depthLevel * 0.97),
      depth_confidence: round4(confidence),
      audio_rms_dbfs: round4(-45 + Math.min(18, flow * 0.75)),
      motion_norm: round4(motion),
      roi_valid: true,
    });
  }

  return samples;
}

export function buildCaptureContractPayload(
  input: BuildCaptureContractInput,
): CaptureContractPayload {
  const model = input.deviceModel?.trim() || "unknown-device";
  const appVersion = input.appVersion?.trim() || "0.1.0";

  return {
    schema_version: "ios_capture_v1",
    session: {
      session_id: input.sessionId,
      sync_id: input.syncId,
      started_at: normalizeStartedAt(input.startedAtIso),
      mode: input.captureMode,
      device: {
        model,
        ios_version: input.iosVersion,
      },
      app: {
        version: appVersion,
      },
      calibration: {
        ml_per_mm: DEFAULT_ML_PER_MM,
        min_depth_confidence: 0.6,
        camera_distance_mm: 650,
      },
      privacy: {
        store_raw_video: false,
        store_raw_audio: false,
        roi_only: true,
      },
    },
    samples: createSamples(input),
  };
}

export function buildCaptureContractPayloadFromSamples(
  input: BuildCaptureContractFromSamplesInput,
): CaptureContractPayload {
  const model = input.deviceModel?.trim() || "unknown-device";
  const appVersion = input.appVersion?.trim() || "0.1.0";
  const source = input.sourceLabel?.trim();
  let safeSamples: CaptureContractSample[] = input.samples;
  if (safeSamples.length === 0) {
    safeSamples = [
      {
        t_s: 0,
        depth_level_mm: 0,
        rgb_level_mm: 0,
        depth_confidence: 0.8,
        audio_rms_dbfs: -55,
        motion_norm: 0.02,
        roi_valid: true,
      },
      {
        t_s: DEFAULT_SAMPLE_STEP_S,
        depth_level_mm: 0.2,
        rgb_level_mm: 0.18,
        depth_confidence: 0.8,
        audio_rms_dbfs: -52,
        motion_norm: 0.02,
        roi_valid: true,
      },
    ];
  } else if (safeSamples.length === 1) {
    safeSamples = [
      { ...safeSamples[0], t_s: 0 },
      {
        ...safeSamples[0],
        t_s: DEFAULT_SAMPLE_STEP_S,
      },
    ];
  }
  const analysis = sanitizeAnalysis(input.analysis);

  const payload: CaptureContractPayload = {
    schema_version: "ios_capture_v1",
    session: {
      session_id: input.sessionId,
      sync_id: input.syncId,
      started_at: normalizeStartedAt(input.startedAtIso),
      mode: input.captureMode,
      device: {
        model: source ? `${model}-${source}` : model,
        ios_version: input.iosVersion,
      },
      app: {
        version: appVersion,
      },
      calibration: {
        ml_per_mm: DEFAULT_ML_PER_MM,
        min_depth_confidence: input.minDepthConfidence ?? 0.6,
        camera_distance_mm: input.cameraDistanceMm ?? 650,
      },
      privacy: {
        store_raw_video: false,
        store_raw_audio: false,
        roi_only: true,
      },
    },
    samples: safeSamples,
  };
  if (analysis) {
    payload.analysis = analysis;
  }
  return payload;
}
