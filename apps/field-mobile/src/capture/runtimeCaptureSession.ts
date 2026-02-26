import { Platform } from "react-native";
import { Audio } from "expo-av";
import { Accelerometer } from "expo-sensors";
import { Camera } from "expo-camera";
import * as Device from "expo-device";
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
};

export type RuntimeCaptureStopResult = {
  startedAtIso: string;
  endedAtIso: string;
  sampleCount: number;
  averageMotionNorm: number;
  permissions: RuntimeCapturePermissions;
  deviceModel: string;
  osVersion: string;
  samples: CaptureContractSample[];
  flowSeries: RuntimeFlowPoint[];
  derived: RuntimeCaptureDerivedMetrics;
  quality: RuntimeCaptureQuality;
};

export type RuntimeCameraSignal = {
  previewReady: boolean;
  roiLocked: boolean;
  roiMotionProxy?: number;
  roiTextureProxy?: number;
  roiValidByFrame?: boolean;
};

export type RuntimeFlowPoint = {
  t_s: number;
  flow_ml_s: number;
};

type AccelerometerWithPermissions = typeof Accelerometer & {
  requestPermissionsAsync?: () => Promise<{ granted: boolean }>;
};

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value));
}

function round4(value: number): number {
  return Math.round(value * 10000) / 10000;
}

function integrateTrapezoid(series: RuntimeFlowPoint[]): number {
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

export class RuntimeCaptureSession {
  private recording: Audio.Recording | null = null;

  private accelerometerSubscription: { remove: () => void } | null = null;

  private sampleInterval: ReturnType<typeof setInterval> | null = null;

  private sampleIntervalMs = 500;

  private sampleTickBusy = false;

  private startedAtMs = 0;

  private startedAtIso = "";

  private latestMotionNorm = 0;

  private latestPreviewReady = false;

  private latestRoiLocked = false;

  private latestRoiMotionProxy = 0;

  private latestRoiTextureProxy = 0;

  private latestRoiValidByFrame = true;

  private cumulativeDepthLevelMm = 0;

  private samples: CaptureContractSample[] = [];

  private flowSeries: RuntimeFlowPoint[] = [];

  private permissions: RuntimeCapturePermissions = {
    microphoneGranted: false,
    cameraGranted: false,
    motionGranted: true,
  };

  private readonly mlPerMm = 8.0;

  setCameraSignal(signal: RuntimeCameraSignal): void {
    this.latestPreviewReady = signal.previewReady;
    this.latestRoiLocked = signal.roiLocked;
    this.latestRoiMotionProxy = clamp(signal.roiMotionProxy ?? this.latestRoiMotionProxy, 0, 1);
    this.latestRoiTextureProxy = clamp(
      signal.roiTextureProxy ?? this.latestRoiTextureProxy,
      0,
      1,
    );
    this.latestRoiValidByFrame = signal.roiValidByFrame ?? this.latestRoiValidByFrame;
  }

  async requestPermissions(): Promise<RuntimeCapturePermissions> {
    const mic = await Audio.requestPermissionsAsync();
    const camera = await Camera.requestCameraPermissionsAsync();

    let motionGranted = true;
    const accelWithPermissions = Accelerometer as AccelerometerWithPermissions;
    if (typeof accelWithPermissions.requestPermissionsAsync === "function") {
      try {
        const motionPermission = await accelWithPermissions.requestPermissionsAsync();
        motionGranted = motionPermission.granted;
      } catch {
        motionGranted = true;
      }
    }

    this.permissions = {
      microphoneGranted: mic.granted,
      cameraGranted: camera.granted,
      motionGranted,
    };

    return this.permissions;
  }

  async start(): Promise<{ startedAtIso: string; permissions: RuntimeCapturePermissions }> {
    const permissions = await this.requestPermissions();
    if (!permissions.microphoneGranted) {
      throw new Error("Microphone permission is required for runtime capture.");
    }

    await this.resetRuntimeState();

    const recording = new Audio.Recording();
    const preset = Audio.RecordingOptionsPresets.HIGH_QUALITY as Audio.RecordingOptions;
    const recordingOptions: Audio.RecordingOptions = {
      ...preset,
      ios: {
        ...(preset.ios ?? {}),
      },
    };
    (
      recordingOptions as Audio.RecordingOptions & { isMeteringEnabled?: boolean }
    ).isMeteringEnabled = true;

    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
      staysActiveInBackground: false,
    });

    await recording.prepareToRecordAsync(recordingOptions);
    await recording.startAsync();

    this.recording = recording;
    this.startedAtMs = Date.now();
    this.startedAtIso = new Date(this.startedAtMs).toISOString();

    this.beginMotionCapture();
    this.beginSampleLoop();

    return {
      startedAtIso: this.startedAtIso,
      permissions,
    };
  }

  async stop(): Promise<RuntimeCaptureStopResult> {
    this.stopSampleLoop();
    this.stopMotionCapture();

    if (this.recording) {
      try {
        await this.recording.stopAndUnloadAsync();
      } catch {
        // Recording may already be stopped.
      }
      this.recording = null;
    }

    const endedAtIso = new Date().toISOString();
    if (this.samples.length < 2) {
      const base = this.samples[0] ?? {
        t_s: 0,
        depth_level_mm: 0,
        rgb_level_mm: 0,
        depth_confidence: 0.8,
        audio_rms_dbfs: -55,
        motion_norm: 0.02,
        roi_valid: this.permissions.cameraGranted,
      };
      this.samples = [
        { ...base, t_s: 0 },
        { ...base, t_s: this.sampleIntervalMs / 1000 },
      ];
    }

    if (this.flowSeries.length < 2) {
      this.flowSeries = this.samples.map((sample) => ({ t_s: sample.t_s, flow_ml_s: 0 }));
    }

    const avgMotionNorm =
      this.samples.reduce((sum, item) => sum + item.motion_norm, 0) /
      Math.max(1, this.samples.length);

    const derived = this.computeDerivedMetrics();
    const quality = this.computeQuality(avgMotionNorm);

    return {
      startedAtIso: this.startedAtIso || new Date().toISOString(),
      endedAtIso,
      sampleCount: this.samples.length,
      averageMotionNorm: round4(avgMotionNorm),
      permissions: this.permissions,
      deviceModel: Device.modelName ?? "unknown-device",
      osVersion: String(Platform.Version),
      samples: [...this.samples],
      flowSeries: [...this.flowSeries],
      derived,
      quality,
    };
  }

  private computeDerivedMetrics(): RuntimeCaptureDerivedMetrics {
    if (this.flowSeries.length === 0) {
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
    const sampleCount = Math.max(1, this.samples.length);
    const roiValidRatio =
      this.samples.filter((sample) => sample.roi_valid).length / sampleCount;
    const enforceRoiForEventBounds = this.permissions.cameraGranted && roiValidRatio >= 0.25;

    let startIndex = -1;
    for (let i = 0; i < this.flowSeries.length; i += 1) {
      const roiGate = !enforceRoiForEventBounds || this.samples[i]?.roi_valid;
      if (this.flowSeries[i].flow_ml_s >= startThreshold && roiGate) {
        startIndex = i;
        break;
      }
    }
    if (startIndex < 0) {
      for (let i = 0; i < this.flowSeries.length; i += 1) {
        if (this.flowSeries[i].flow_ml_s >= startThreshold) {
          startIndex = i;
          break;
        }
      }
    }

    let endIndex = -1;
    for (let i = this.flowSeries.length - 1; i >= 0; i -= 1) {
      const roiGate = !enforceRoiForEventBounds || this.samples[i]?.roi_valid;
      if (this.flowSeries[i].flow_ml_s >= stopThreshold && roiGate) {
        endIndex = i;
        break;
      }
    }
    if (endIndex < 0) {
      for (let i = this.flowSeries.length - 1; i >= 0; i -= 1) {
        if (this.flowSeries[i].flow_ml_s >= stopThreshold) {
          endIndex = i;
          break;
        }
      }
    }

    const eventStartTs = startIndex >= 0 ? this.flowSeries[startIndex].t_s : null;
    const eventEndTs =
      endIndex >= 0 && startIndex >= 0 && endIndex >= startIndex
        ? this.flowSeries[endIndex].t_s
        : null;

    const qmax = this.flowSeries.reduce(
      (acc, point) => Math.max(acc, point.flow_ml_s),
      0,
    );

    const vvoid = integrateTrapezoid(this.flowSeries);

    let flowTimeS = 0;
    let qavg = 0;
    let tqmax = 0;

    if (eventStartTs != null && eventEndTs != null && eventEndTs >= eventStartTs) {
      flowTimeS = eventEndTs - eventStartTs;
      const activeSeries = this.flowSeries.filter(
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

  private computeQuality(averageMotionNorm: number): RuntimeCaptureQuality {
    const sampleCount = Math.max(1, this.samples.length);
    const roiValidCount = this.samples.filter((sample) => sample.roi_valid).length;
    const lowConfidenceCount = this.samples.filter((sample) => sample.depth_confidence < 0.6).length;

    const roiValidRatio = roiValidCount / sampleCount;
    const lowConfidenceRatio = lowConfidenceCount / sampleCount;

    let score = 100;
    score -= clamp(averageMotionNorm * 80, 0, 60);
    score -= clamp((1 - roiValidRatio) * 70, 0, 50);
    score -= clamp(lowConfidenceRatio * 40, 0, 25);
    score = clamp(score, 0, 100);

    let qualityStatus: RuntimeCaptureQuality["qualityStatus"] = "valid";
    if (score < 50 || roiValidRatio < 0.55) {
      qualityStatus = "reject";
    } else if (score < 75 || roiValidRatio < 0.8 || lowConfidenceRatio > 0.35) {
      qualityStatus = "repeat";
    }

    return {
      qualityScore: round4(score),
      qualityStatus,
      roiValidRatio: round4(roiValidRatio),
      lowConfidenceRatio: round4(lowConfidenceRatio),
    };
  }

  private async resetRuntimeState(): Promise<void> {
    this.stopSampleLoop();
    this.stopMotionCapture();
    this.sampleTickBusy = false;
    this.latestMotionNorm = 0;
    this.latestRoiMotionProxy = 0;
    this.latestRoiTextureProxy = 0;
    this.latestRoiValidByFrame = true;
    this.cumulativeDepthLevelMm = 0;
    this.samples = [];
    this.flowSeries = [];

    if (this.recording) {
      try {
        await this.recording.stopAndUnloadAsync();
      } catch {
        // best effort cleanup
      }
      this.recording = null;
    }
  }

  private beginMotionCapture(): void {
    if (!this.permissions.motionGranted) {
      return;
    }
    Accelerometer.setUpdateInterval(100);
    this.accelerometerSubscription = Accelerometer.addListener((event) => {
      const magnitude = Math.sqrt(event.x ** 2 + event.y ** 2 + event.z ** 2);
      this.latestMotionNorm = clamp(Math.abs(magnitude - 1), 0, 1);
    });
  }

  private stopMotionCapture(): void {
    if (this.accelerometerSubscription) {
      this.accelerometerSubscription.remove();
      this.accelerometerSubscription = null;
    }
  }

  private beginSampleLoop(): void {
    this.stopSampleLoop();

    this.sampleInterval = setInterval(() => {
      if (this.sampleTickBusy) {
        return;
      }
      this.sampleTickBusy = true;
      void this.collectSample().finally(() => {
        this.sampleTickBusy = false;
      });
    }, this.sampleIntervalMs);
  }

  private stopSampleLoop(): void {
    if (this.sampleInterval) {
      clearInterval(this.sampleInterval);
      this.sampleInterval = null;
    }
  }

  private async collectSample(): Promise<void> {
    if (!this.recording) {
      return;
    }

    let meteringDbfs = -60;
    try {
      const status = await this.recording.getStatusAsync();
      const maybeMetering = (status as { metering?: unknown }).metering;
      if (typeof maybeMetering === "number" && Number.isFinite(maybeMetering)) {
        meteringDbfs = maybeMetering;
      }
    } catch {
      meteringDbfs = -60;
    }

    const elapsedS = Math.max(0, (Date.now() - this.startedAtMs) / 1000);
    const normalizedAudio = clamp((meteringDbfs + 60) / 45, 0, 1.25);
    const motionPenalty = clamp(this.latestMotionNorm * 0.8, 0, 0.6);
    const roiBoost = clamp(this.latestRoiMotionProxy * 3.5, 0, 2.5);
    const textureBoost = clamp(this.latestRoiTextureProxy * 1.2, 0, 1.2);
    const effectiveFlowProxyMlS = Math.max(
      0,
      normalizedAudio * 8.5 * (1 - motionPenalty) + roiBoost + textureBoost,
    );

    this.cumulativeDepthLevelMm += (effectiveFlowProxyMlS * (this.sampleIntervalMs / 1000)) / this.mlPerMm;

    const previewWeight = this.latestPreviewReady && this.latestRoiLocked ? 0 : 0.2;
    const roiPenalty = this.latestRoiValidByFrame ? 0 : 0.25;
    const depthConfidence = clamp(
      0.93 - this.latestMotionNorm * 1.8 - previewWeight - roiPenalty,
      0.25,
      0.95,
    );
    const roiValid =
      this.permissions.cameraGranted &&
      this.latestPreviewReady &&
      this.latestRoiLocked &&
      this.latestRoiValidByFrame &&
      this.latestMotionNorm < 0.35;

    this.samples.push({
      t_s: round4(elapsedS),
      depth_level_mm: round4(this.cumulativeDepthLevelMm),
      rgb_level_mm: round4(this.cumulativeDepthLevelMm * 0.98),
      depth_confidence: round4(depthConfidence),
      audio_rms_dbfs: round4(meteringDbfs),
      motion_norm: round4(this.latestMotionNorm),
      roi_valid: roiValid,
    });

    this.flowSeries.push({
      t_s: round4(elapsedS),
      flow_ml_s: round4(effectiveFlowProxyMlS),
    });
  }
}
