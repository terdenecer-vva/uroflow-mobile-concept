import { buildCaptureContractPayload } from "../capture/buildCaptureContract";
import type { CapturePackagePayload, PairedPayload } from "../types";
import { runtimeCaptureMatchesSession } from "../utils/appHelpers";

export type BuildCapturePackagePayloadOptions = {
  currentPayload: PairedPayload;
  pairedMeasurementId: number | null;
  runtimeCaptureContractPayload: Record<string, unknown> | null;
  platformVersion: string;
};

export function buildCapturePackagePayloadFromPaired({
  currentPayload,
  pairedMeasurementId,
  runtimeCaptureContractPayload,
  platformVersion,
}: BuildCapturePackagePayloadOptions): CapturePackagePayload {
  let captureContractPayload: Record<string, unknown>;
  let notes = "mobile_scaffold_capture_contract_v0.1";

  if (
    runtimeCaptureContractPayload &&
    runtimeCaptureMatchesSession(runtimeCaptureContractPayload, currentPayload.session)
  ) {
    captureContractPayload = runtimeCaptureContractPayload;
    notes = "mobile_runtime_capture_contract_audio_imu_v0.1";
  } else {
    captureContractPayload = buildCaptureContractPayload({
      sessionId: currentPayload.session.session_id,
      syncId: currentPayload.session.sync_id,
      startedAtIso: currentPayload.session.measured_at,
      captureMode: currentPayload.session.capture_mode,
      deviceModel: currentPayload.session.device_model,
      iosVersion: platformVersion,
      appVersion: currentPayload.session.app_version,
      qmaxMlS: currentPayload.app.metrics.qmax_ml_s,
      qavgMlS: currentPayload.app.metrics.qavg_ml_s,
      flowTimeS: currentPayload.app.metrics.flow_time_s,
    }) as unknown as Record<string, unknown>;
  }

  return {
    session: currentPayload.session,
    package_type: "capture_contract_json",
    capture_payload: captureContractPayload,
    paired_measurement_id: pairedMeasurementId,
    notes,
  };
}
