export const APP_RUNTIME_MODE = "pilot";
export const APP_DEFAULT_CAPTURE_MODE = "water_impact";
export const APP_STORE_RAW_VIDEO = false;
export const APP_STORE_RAW_AUDIO = false;
export const APP_ROI_ONLY = true;

export const APP_PRIVACY_POLICY = Object.freeze({
  storeRawVideo: APP_STORE_RAW_VIDEO,
  storeRawAudio: APP_STORE_RAW_AUDIO,
  roiOnly: APP_ROI_ONLY,
});

export const APP_RUNTIME_CONFIG = Object.freeze({
  runtimeMode: APP_RUNTIME_MODE,
  defaultCaptureMode: APP_DEFAULT_CAPTURE_MODE,
  privacyPolicy: APP_PRIVACY_POLICY,
});
