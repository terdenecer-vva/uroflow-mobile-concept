import type { PendingEndpoint } from "../types";

export const APP_RUNTIME_MODE = "pilot";
export const APP_ENDPOINT_SET = "clinical_hub_v1";
export const APP_DEFAULT_CAPTURE_MODE = "water_impact";
export const APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH = "/api/v1/paired-measurements";
export const APP_CAPTURE_PACKAGES_ENDPOINT_PATH = "/api/v1/capture-packages";
export const APP_STORE_RAW_VIDEO = false;
export const APP_STORE_RAW_AUDIO = false;
export const APP_ROI_ONLY = true;
export const APP_ALLOW_DEBUG_CONTROLS = false;
export const APP_ALLOW_RAW_RESPONSE_DETAILS = false;
export const APP_ENABLE_VERBOSE_LOGGING = false;

export const APP_ENDPOINT_PATHS: Readonly<Record<PendingEndpoint, string>> = Object.freeze({
  paired_measurements: APP_PAIRED_MEASUREMENTS_ENDPOINT_PATH,
  capture_packages: APP_CAPTURE_PACKAGES_ENDPOINT_PATH,
});

export const APP_PRIVACY_POLICY = Object.freeze({
  storeRawVideo: APP_STORE_RAW_VIDEO,
  storeRawAudio: APP_STORE_RAW_AUDIO,
  roiOnly: APP_ROI_ONLY,
});

export const APP_DEBUG_GATES = Object.freeze({
  allowDebugControls: APP_ALLOW_DEBUG_CONTROLS,
  allowRawResponseDetails: APP_ALLOW_RAW_RESPONSE_DETAILS,
  enableVerboseLogging: APP_ENABLE_VERBOSE_LOGGING,
});

export const APP_RUNTIME_CONFIG = Object.freeze({
  runtimeMode: APP_RUNTIME_MODE,
  endpointSet: APP_ENDPOINT_SET,
  endpointPaths: APP_ENDPOINT_PATHS,
  defaultCaptureMode: APP_DEFAULT_CAPTURE_MODE,
  privacyPolicy: APP_PRIVACY_POLICY,
  debugGates: APP_DEBUG_GATES,
});
