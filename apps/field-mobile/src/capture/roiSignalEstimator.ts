export type RoiSignalEstimatorInput = {
  frameBase64: string;
  prevHash: number | null;
  prevLength: number | null;
};

export type RoiSignalEstimatorOutput = {
  frameHash: number;
  frameLength: number;
  motionProxy: number;
  textureProxy: number;
  roiValid: boolean;
};

function clamp(value: number, minValue: number, maxValue: number): number {
  return Math.max(minValue, Math.min(maxValue, value));
}

function sampleHash(base64: string): number {
  let hash = 2166136261 >>> 0;
  const step = Math.max(1, Math.floor(base64.length / 256));
  for (let i = 0; i < base64.length; i += step) {
    hash ^= base64.charCodeAt(i);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

function sampleTextureProxy(base64: string): number {
  if (base64.length === 0) {
    return 0;
  }
  const bins = new Array<number>(16).fill(0);
  const step = Math.max(1, Math.floor(base64.length / 512));
  let sampleCount = 0;
  for (let i = 0; i < base64.length; i += step) {
    const code = base64.charCodeAt(i) & 0x0f;
    bins[code] += 1;
    sampleCount += 1;
  }
  if (sampleCount <= 1) {
    return 0;
  }

  let entropy = 0;
  for (const count of bins) {
    if (count <= 0) {
      continue;
    }
    const p = count / sampleCount;
    entropy -= p * Math.log2(p);
  }
  const maxEntropy = Math.log2(bins.length);
  return clamp(entropy / maxEntropy, 0, 1);
}

export function estimateRoiSignalFromBase64(
  input: RoiSignalEstimatorInput,
): RoiSignalEstimatorOutput {
  const frameLength = input.frameBase64.length;
  const frameHash = sampleHash(input.frameBase64);
  const textureProxy = sampleTextureProxy(input.frameBase64);

  let motionProxy = 0;
  if (input.prevHash != null) {
    const hashDelta = Math.abs(frameHash - input.prevHash) / 0xffffffff;
    const lenDelta =
      input.prevLength != null && input.prevLength > 0
        ? Math.abs(frameLength - input.prevLength) / input.prevLength
        : 0;
    motionProxy = clamp(hashDelta * 1.8 + lenDelta * 1.2, 0, 1);
  }

  const roiValid = textureProxy > 0.18 && motionProxy < 0.92;

  return {
    frameHash,
    frameLength,
    motionProxy,
    textureProxy,
    roiValid,
  };
}
