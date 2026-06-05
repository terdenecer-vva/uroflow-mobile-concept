import type { CaptureContractSample } from "./buildCaptureContract";

export type RuntimeCapturePermissions = {
  microphoneGranted: boolean;
  cameraGranted: boolean;
  motionGranted: boolean;
};

export type RuntimeCaptureDerivedMetrics = {
  qmaxMlS: number;
  qavgMlS: number;
  vvoidMl: number;
  flowTimeS: number;
  tqmaxS: number;
  eventStartTs: number | null;
  eventEndTs: number | null;
};

export type RuntimeCaptureQuality = {
  qualityScore: number;
  qualityStatus: "valid" | "repeat" | "reject";
  roiValidRatio: number;
  lowConfidenceRatio: number;
  highMotionRatio: number;
};

export type RuntimeFlowPoint = {
  t_s: number;
  flow_ml_s: number;
};

export type RuntimeCaptureReadinessCode =
  | "ready"
  | "camera_permission_missing"
  | "camera_preview_not_ready"
  | "roi_not_locked"
  | "roi_frame_not_validated"
  | "roi_frame_invalid";

export type RuntimeCaptureReadiness = {
  ready: boolean;
  code: RuntimeCaptureReadinessCode;
  message: string;
};

export const HIGH_MOTION_SAMPLE_THRESHOLD = 0.35;
const HIGH_MOTION_REPEAT_RATIO = 0.2;
const HIGH_MOTION_REJECT_RATIO = 0.45;

export function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value));
}

export function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

export function calculateAverageMotionNorm(samples: CaptureContractSample[]): number {
  return (
    samples.reduce((sum, item) => sum + item.motion_norm, 0) / Math.max(1, samples.length)
  );
}

export function integrateRuntimeFlowSeries(series: RuntimeFlowPoint[]): number {
  if (series.length < 2) {
    return 0;
  }
  let sum = 0;
  for (let index = 1; index < series.length; index += 1) {
    const prev = series[index - 1];
    const curr = series[index];
    const dt = Math.max(0, curr.t_s - prev.t_s);
    sum += ((prev.flow_ml_s + curr.flow_ml_s) * 0.5) * dt;
  }
  return sum;
}

export function buildRuntimeCaptureReadiness(input: {
  cameraPermissionGranted: boolean;
  cameraPreviewReady: boolean;
  roiLocked: boolean;
  roiFrameCount: number;
  roiFrameValid: boolean;
}): RuntimeCaptureReadiness {
  if (!input.cameraPermissionGranted) {
    return {
      ready: false,
      code: "camera_permission_missing",
      message: "Grant camera permission before starting runtime capture.",
    };
  }
  if (!input.cameraPreviewReady) {
    return {
      ready: false,
      code: "camera_preview_not_ready",
      message: "Wait for the camera preview to become ready before starting runtime capture.",
    };
  }
  if (!input.roiLocked) {
    return {
      ready: false,
      code: "roi_not_locked",
      message: "Lock ROI before starting runtime capture.",
    };
  }
  if (input.roiFrameCount < 1) {
    return {
      ready: false,
      code: "roi_frame_not_validated",
      message: "Wait for at least one ROI frame validation after locking ROI.",
    };
  }
  if (!input.roiFrameValid) {
    return {
      ready: false,
      code: "roi_frame_invalid",
      message: "Re-aim the phone until ROI frame validity is yes, then start capture.",
    };
  }
  return {
    ready: true,
    code: "ready",
    message: "Runtime capture preflight ready.",
  };
}

export function deriveRuntimeCaptureMetrics(input: {
  samples: CaptureContractSample[];
  flowSeries: RuntimeFlowPoint[];
  permissions: Pick<RuntimeCapturePermissions, "cameraGranted">;
}): RuntimeCaptureDerivedMetrics {
  if (input.flowSeries.length === 0) {
    return {
      qmaxMlS: 0,
      qavgMlS: 0,
      vvoidMl: 0,
      flowTimeS: 0,
      tqmaxS: 0,
      eventStartTs: null,
      eventEndTs: null,
    };
  }

  const startThreshold = 1.0;
  const stopThreshold = 0.8;
  const sampleCount = Math.max(1, input.samples.length);
  const roiValidRatio =
    input.samples.filter((sample) => sample.roi_valid).length / sampleCount;
  const enforceRoiForEventBounds = input.permissions.cameraGranted && roiValidRatio >= 0.25;

  let startIndex = -1;
  for (let i = 0; i < input.flowSeries.length; i += 1) {
    const roiGate = !enforceRoiForEventBounds || input.samples[i]?.roi_valid;
    if (input.flowSeries[i].flow_ml_s >= startThreshold && roiGate) {
      startIndex = i;
      break;
    }
  }
  if (startIndex < 0) {
    for (let i = 0; i < input.flowSeries.length; i += 1) {
      if (input.flowSeries[i].flow_ml_s >= startThreshold) {
        startIndex = i;
        break;
      }
    }
  }

  let endIndex = -1;
  for (let i = input.flowSeries.length - 1; i >= 0; i -= 1) {
    const roiGate = !enforceRoiForEventBounds || input.samples[i]?.roi_valid;
    if (input.flowSeries[i].flow_ml_s >= stopThreshold && roiGate) {
      endIndex = i;
      break;
    }
  }
  if (endIndex < 0) {
    for (let i = input.flowSeries.length - 1; i >= 0; i -= 1) {
      if (input.flowSeries[i].flow_ml_s >= stopThreshold) {
        endIndex = i;
        break;
      }
    }
  }

  const eventStartTs = startIndex >= 0 ? input.flowSeries[startIndex].t_s : null;
  const eventEndTs =
    endIndex >= 0 && startIndex >= 0 && endIndex >= startIndex
      ? input.flowSeries[endIndex].t_s
      : null;

  const qmax = input.flowSeries.reduce(
    (acc, point) => Math.max(acc, point.flow_ml_s),
    0,
  );
  const vvoid = integrateRuntimeFlowSeries(input.flowSeries);

  let flowTimeS = 0;
  let qavg = 0;
  let tqmax = 0;

  if (eventStartTs != null && eventEndTs != null && eventEndTs >= eventStartTs) {
    flowTimeS = eventEndTs - eventStartTs;
    const activeSeries = input.flowSeries.filter(
      (point) => point.t_s >= eventStartTs && point.t_s <= eventEndTs,
    );
    if (activeSeries.length > 0) {
      qavg = activeSeries.reduce((sum, point) => sum + point.flow_ml_s, 0) / activeSeries.length;
      const qmaxPoint = activeSeries.reduce((best, point) =>
        point.flow_ml_s > best.flow_ml_s ? point : best,
      activeSeries[0]);
      tqmax = Math.max(0, qmaxPoint.t_s - eventStartTs);
    }
  }

  return {
    qmaxMlS: round4(qmax),
    qavgMlS: round4(qavg),
    vvoidMl: round4(vvoid),
    flowTimeS: round4(flowTimeS),
    tqmaxS: round4(tqmax),
    eventStartTs,
    eventEndTs,
  };
}

export function scoreRuntimeCaptureQuality(input: {
  samples: CaptureContractSample[];
  averageMotionNorm: number;
}): RuntimeCaptureQuality {
  const sampleCount = Math.max(1, input.samples.length);
  const roiValidCount = input.samples.filter((sample) => sample.roi_valid).length;
  const lowConfidenceCount = input.samples.filter((sample) => sample.depth_confidence < 0.6).length;
  const highMotionCount = input.samples.filter(
    (sample) => sample.motion_norm >= HIGH_MOTION_SAMPLE_THRESHOLD,
  ).length;

  const roiValidRatio = roiValidCount / sampleCount;
  const lowConfidenceRatio = lowConfidenceCount / sampleCount;
  const highMotionRatio = highMotionCount / sampleCount;

  let score = 100;
  score -= clamp(input.averageMotionNorm * 80, 0, 60);
  score -= clamp((1 - roiValidRatio) * 70, 0, 50);
  score -= clamp(lowConfidenceRatio * 40, 0, 25);
  score -= clamp(highMotionRatio * 50, 0, 30);
  score = clamp(score, 0, 100);

  let qualityStatus: RuntimeCaptureQuality["qualityStatus"] = "valid";
  if (score < 50 || roiValidRatio < 0.55 || highMotionRatio > HIGH_MOTION_REJECT_RATIO) {
    qualityStatus = "reject";
  } else if (
    score < 75 ||
    roiValidRatio < 0.8 ||
    lowConfidenceRatio > 0.35 ||
    highMotionRatio > HIGH_MOTION_REPEAT_RATIO
  ) {
    qualityStatus = "repeat";
  }

  return {
    qualityScore: round4(score),
    qualityStatus,
    roiValidRatio: round4(roiValidRatio),
    lowConfidenceRatio: round4(lowConfidenceRatio),
    highMotionRatio: round4(highMotionRatio),
  };
}
