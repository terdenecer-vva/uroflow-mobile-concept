import { Platform } from "react-native";
import {
  AudioModule,
  RecordingPresets,
  requestRecordingPermissionsAsync,
  setAudioModeAsync,
  type AudioRecorder,
  type RecordingOptions,
} from "expo-audio";
import { Accelerometer } from "expo-sensors";
import { Camera } from "expo-camera";
import * as Device from "expo-device";
import type { CaptureContractSample } from "./buildCaptureContract";
import {
  calculateAverageMotionNorm,
  clamp,
  deriveRuntimeCaptureMetrics,
  round4,
  scoreRuntimeCaptureQuality,
  type RuntimeCaptureDerivedMetrics,
  type RuntimeCapturePermissions,
  type RuntimeCaptureQuality,
  type RuntimeFlowPoint,
} from "./runtimeMetrics";

export type {
  RuntimeCaptureDerivedMetrics,
  RuntimeCapturePermissions,
  RuntimeCaptureQuality,
  RuntimeFlowPoint,
} from "./runtimeMetrics";

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

type AccelerometerWithPermissions = typeof Accelerometer & {
  requestPermissionsAsync?: () => Promise<{ granted: boolean }>;
};

export class RuntimeCaptureSession {
  private recording: AudioRecorder | null = null;

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
    const mic = await requestRecordingPermissionsAsync();
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

    const recordingOptions: RecordingOptions = {
      ...RecordingPresets.HIGH_QUALITY,
      isMeteringEnabled: true,
    };

    await setAudioModeAsync({
      allowsRecording: true,
      playsInSilentMode: true,
      shouldRouteThroughEarpiece: false,
      shouldPlayInBackground: false,
      allowsBackgroundRecording: false,
      interruptionMode: "duckOthers",
    });

    const recording = new AudioModule.AudioRecorder(recordingOptions);
    await recording.prepareToRecordAsync(recordingOptions);
    recording.record();

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
        await this.recording.stop();
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

    const avgMotionNorm = calculateAverageMotionNorm(this.samples);
    const derived = deriveRuntimeCaptureMetrics({
      samples: this.samples,
      flowSeries: this.flowSeries,
      permissions: this.permissions,
    });
    const quality = scoreRuntimeCaptureQuality({
      samples: this.samples,
      averageMotionNorm: avgMotionNorm,
    });

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
        await this.recording.stop();
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
      const maybeMetering = this.recording.getStatus().metering;
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
