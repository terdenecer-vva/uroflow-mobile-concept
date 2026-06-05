export type DeviceIdentityInput = {
  platform: string;
  modelName?: string | null;
  manufacturer?: string | null;
  brand?: string | null;
  osName?: string | null;
  osVersion?: string | null;
  platformVersion?: string | number | null;
};

function clean(value: string | number | null | undefined): string {
  return String(value ?? "").trim();
}

function joinUnique(parts: string[]): string {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const part of parts) {
    const normalized = clean(part);
    if (!normalized || seen.has(normalized.toLowerCase())) {
      continue;
    }
    seen.add(normalized.toLowerCase());
    result.push(normalized);
  }
  return result.join(" ");
}

export function buildDeviceModelLabel(input: DeviceIdentityInput): string {
  const modelName = clean(input.modelName);
  if (modelName) {
    return modelName;
  }

  const manufacturerModel = joinUnique([clean(input.manufacturer), clean(input.brand)]);
  if (manufacturerModel) {
    return manufacturerModel;
  }

  const platform = clean(input.platform) || "unknown";
  return `${platform}-device`;
}

export function buildDeviceOsVersion(input: DeviceIdentityInput): string {
  const osName = clean(input.osName);
  const osVersion = clean(input.osVersion);
  if (osName && osVersion) {
    return `${osName} ${osVersion}`;
  }
  if (osVersion) {
    return osVersion;
  }
  if (osName) {
    return osName;
  }
  const platformVersion = clean(input.platformVersion);
  return platformVersion || "unknown-os";
}
