import { APP_RUNTIME_CONFIG } from "./appConfig";
import { APP_RELEASE_METADATA } from "./releaseMetadata";

export const SUPPORTED_CAPTURE_SCHEMA_VERSIONS = Object.freeze(["ios_capture_v1"]);

export type RuntimeReleaseGuardStatus = "pass" | "blocked";

export type RuntimeReleaseGuardResult = {
  status: RuntimeReleaseGuardStatus;
  blockers: string[];
  message: string;
  evidence: string;
};

type ReleaseMetadataLike = typeof APP_RELEASE_METADATA;
type RuntimeConfigLike = typeof APP_RUNTIME_CONFIG;

type RuntimeReleaseGuardInput = {
  releaseMetadata?: ReleaseMetadataLike;
  runtimeConfig?: RuntimeConfigLike;
  supportedCaptureSchemaVersions?: readonly string[];
};

function normalized(value: string | null | undefined): string {
  return typeof value === "string" ? value.trim() : "";
}

function addBlocker(blockers: string[], condition: boolean, blocker: string): void {
  if (!condition) {
    blockers.push(blocker);
  }
}

export function buildRuntimeReleaseGuard(
  input: RuntimeReleaseGuardInput = {},
): RuntimeReleaseGuardResult {
  const releaseMetadata = input.releaseMetadata ?? APP_RELEASE_METADATA;
  const runtimeConfig = input.runtimeConfig ?? APP_RUNTIME_CONFIG;
  const supportedCaptureSchemaVersions =
    input.supportedCaptureSchemaVersions ?? SUPPORTED_CAPTURE_SCHEMA_VERSIONS;
  const blockers: string[] = [];

  const appVersion = normalized(releaseMetadata.appVersion);
  const modelId = normalized(releaseMetadata.modelId);
  const captureSchemaVersion = normalized(releaseMetadata.captureSchemaVersion);
  const pairedEndpoint = runtimeConfig.endpointPaths.paired_measurements;
  const captureEndpoint = runtimeConfig.endpointPaths.capture_packages;

  addBlocker(blockers, appVersion.length > 0, "app_version_missing");
  addBlocker(blockers, modelId.length > 0, "model_id_missing");
  addBlocker(
    blockers,
    supportedCaptureSchemaVersions.includes(captureSchemaVersion),
    "capture_schema_unsupported",
  );
  addBlocker(blockers, runtimeConfig.runtimeMode === "pilot", "runtime_mode_mismatch");
  addBlocker(blockers, runtimeConfig.endpointSet === "clinical_hub_v1", "endpoint_set_mismatch");
  addBlocker(
    blockers,
    runtimeConfig.defaultCaptureMode === "water_impact",
    "default_capture_mode_mismatch",
  );
  addBlocker(
    blockers,
    pairedEndpoint === "/api/v1/paired-measurements",
    "paired_endpoint_mismatch",
  );
  addBlocker(
    blockers,
    captureEndpoint === "/api/v1/capture-packages",
    "capture_endpoint_mismatch",
  );
  addBlocker(
    blockers,
    runtimeConfig.privacyPolicy.storeRawVideo === false &&
      runtimeConfig.privacyPolicy.storeRawAudio === false &&
      runtimeConfig.privacyPolicy.roiOnly === true,
    "privacy_policy_mismatch",
  );
  addBlocker(
    blockers,
    runtimeConfig.dataResidencyPolicy.region === "us" &&
      runtimeConfig.dataResidencyPolicy.boundary === "single_region" &&
      runtimeConfig.dataResidencyPolicy.allowCrossRegionSync === false &&
      runtimeConfig.dataResidencyPolicy.requireRegionMatchedClinicalHub === true,
    "data_residency_policy_mismatch",
  );
  addBlocker(
    blockers,
    runtimeConfig.debugGates.allowDebugControls === false &&
      runtimeConfig.debugGates.allowRawResponseDetails === false &&
      runtimeConfig.debugGates.enableVerboseLogging === false,
    "debug_gates_enabled",
  );

  const status: RuntimeReleaseGuardStatus = blockers.length === 0 ? "pass" : "blocked";
  const evidence = [
    `app_version=${appVersion || "blank"}`,
    `model_id=${modelId || "blank"}`,
    `capture_schema=${captureSchemaVersion || "blank"}`,
    `runtime_mode=${runtimeConfig.runtimeMode}`,
    `endpoint_set=${runtimeConfig.endpointSet}`,
    `default_capture_mode=${runtimeConfig.defaultCaptureMode}`,
    `paired_endpoint=${pairedEndpoint}`,
    `capture_endpoint=${captureEndpoint}`,
    `privacy=raw_video_${runtimeConfig.privacyPolicy.storeRawVideo ? "on" : "off"}/raw_audio_${
      runtimeConfig.privacyPolicy.storeRawAudio ? "on" : "off"
    }/roi_only_${runtimeConfig.privacyPolicy.roiOnly ? "on" : "off"}`,
    `data_residency=${runtimeConfig.dataResidencyPolicy.region}/${runtimeConfig.dataResidencyPolicy.boundary}`,
    `cross_region_sync=${runtimeConfig.dataResidencyPolicy.allowCrossRegionSync ? "on" : "off"}`,
    `debug_gates=${
      runtimeConfig.debugGates.allowDebugControls ||
      runtimeConfig.debugGates.allowRawResponseDetails ||
      runtimeConfig.debugGates.enableVerboseLogging
        ? "on"
        : "off"
    }`,
  ].join("; ");

  return {
    status,
    blockers,
    evidence,
    message:
      status === "pass"
        ? "Runtime release guard passed. Model, schema, endpoints, privacy, and residency are aligned."
        : `Runtime release guard blocked: ${blockers.join(", ")}`,
  };
}

export function isRuntimeReleaseGuardActionAllowed(
  guard: RuntimeReleaseGuardResult,
): boolean {
  return guard.status === "pass";
}
