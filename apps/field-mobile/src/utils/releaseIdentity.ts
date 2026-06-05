import { APP_RUNTIME_CONFIG } from "../config/appConfig";
import { APP_RELEASE_METADATA } from "../config/releaseMetadata";
import { buildRuntimeReleaseGuard } from "../config/runtimeReleaseGuard";

export type ReleaseIdentityRow = {
  label: string;
  value: string;
};

export type ReleaseIdentityStatus = "aligned" | "edited";

export type ReleaseIdentitySnapshot = {
  platform: string;
  canonicalRows: ReleaseIdentityRow[];
  payloadStatus: ReleaseIdentityStatus;
  payloadEvidence: string;
  releaseGuardStatus: "pass" | "blocked";
  releaseGuardEvidence: string;
  releaseGuardBlockers: string[];
  artifactTraceabilityNote: string;
};

type BuildReleaseIdentitySnapshotOptions = {
  platform?: string;
  payloadAppVersion: string;
  payloadModelId: string;
  payloadCaptureMode: string;
};

function formatFlag(value: boolean): string {
  return value ? "on" : "off";
}

function normalize(value: string): string {
  return value.trim();
}

export function buildReleaseIdentitySnapshot(
  options: BuildReleaseIdentitySnapshotOptions,
): ReleaseIdentitySnapshot {
  const platform = options.platform?.trim() || "unknown";
  const payloadAppVersion = normalize(options.payloadAppVersion);
  const payloadModelId = normalize(options.payloadModelId);
  const payloadCaptureMode = normalize(options.payloadCaptureMode);
  const privacy = APP_RUNTIME_CONFIG.privacyPolicy;
  const residency = APP_RUNTIME_CONFIG.dataResidencyPolicy;
  const debug = APP_RUNTIME_CONFIG.debugGates;
  const releaseGuard = buildRuntimeReleaseGuard();
  const payloadAligned =
    payloadAppVersion === APP_RELEASE_METADATA.appVersion &&
    payloadModelId === APP_RELEASE_METADATA.modelId &&
    payloadCaptureMode === APP_RUNTIME_CONFIG.defaultCaptureMode;

  return {
    platform,
    canonicalRows: [
      { label: "App version", value: APP_RELEASE_METADATA.appVersion },
      { label: "Model ID", value: APP_RELEASE_METADATA.modelId },
      { label: "Capture schema", value: APP_RELEASE_METADATA.captureSchemaVersion },
      { label: "Runtime mode", value: APP_RUNTIME_CONFIG.runtimeMode },
      { label: "Endpoint set", value: APP_RUNTIME_CONFIG.endpointSet },
      { label: "Default capture mode", value: APP_RUNTIME_CONFIG.defaultCaptureMode },
      {
        label: "Privacy",
        value: `raw video ${formatFlag(privacy.storeRawVideo)}, raw audio ${formatFlag(
          privacy.storeRawAudio,
        )}, ROI-only ${formatFlag(privacy.roiOnly)}`,
      },
      {
        label: "Data residency",
        value: `${residency.region}/${residency.boundary}, cross-region sync ${formatFlag(
          residency.allowCrossRegionSync,
        )}`,
      },
      {
        label: "Debug gates",
        value: `debug controls ${formatFlag(debug.allowDebugControls)}, raw details ${formatFlag(
          debug.allowRawResponseDetails,
        )}, verbose logs ${formatFlag(debug.enableVerboseLogging)}`,
      },
      { label: "Device platform", value: platform },
    ],
    payloadStatus: payloadAligned ? "aligned" : "edited",
    payloadEvidence: payloadAligned
      ? "Payload app version, model ID, and capture mode match release metadata."
      : [
          `Payload app_version=${payloadAppVersion || "blank"}`,
          `model_id=${payloadModelId || "blank"}`,
          `capture_mode=${payloadCaptureMode || "blank"}`,
          "do not match canonical release metadata.",
        ].join("; "),
    releaseGuardStatus: releaseGuard.status,
    releaseGuardEvidence: releaseGuard.message,
    releaseGuardBlockers: releaseGuard.blockers,
    artifactTraceabilityNote:
      "Git SHA, run ID, signing status, and store rollout evidence are tracked in Mobile Build artifacts.",
  };
}
