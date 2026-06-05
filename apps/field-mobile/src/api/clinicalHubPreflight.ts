import {
  APP_ALLOW_CROSS_REGION_SYNC,
  APP_DATA_RESIDENCY_REGION,
  APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB,
} from "../config/appConfig";
import { buildBaseUrl, buildMissingApiBaseUrlMessage } from "./clinicalHub";

export type ClinicalHubPreflightStatus = "pass" | "warning" | "blocked";

export type ClinicalHubPreflightCode =
  | "configured"
  | "insecure_transport"
  | "local_dev"
  | "missing_url"
  | "region_mismatch"
  | "region_unknown"
  | "unsupported_url";

export type ClinicalHubPreflightResult = {
  status: ClinicalHubPreflightStatus;
  code: ClinicalHubPreflightCode;
  message: string;
  normalizedBaseUrl: string;
  expectedRegion: string;
  inferredRegion: string | null;
};

const REGION_ALIASES: Readonly<Record<string, string>> = Object.freeze({
  au: "au",
  ca: "ca",
  cn: "cn",
  eu: "eu",
  uk: "uk",
  us: "us",
  usa: "us",
});

function tokenizeHostname(hostname: string): string[] {
  return hostname.toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

export function inferClinicalHubRegionFromHostname(hostname: string): string | null {
  for (const token of tokenizeHostname(hostname)) {
    const region = REGION_ALIASES[token];
    if (region) {
      return region;
    }
  }
  return null;
}

export function isLocalClinicalHubHostname(hostname: string): boolean {
  const normalized = hostname.toLowerCase();
  if (
    normalized === "localhost" ||
    normalized === "0.0.0.0" ||
    normalized === "::1" ||
    normalized === "[::1]" ||
    normalized.endsWith(".local") ||
    normalized.startsWith("127.")
  ) {
    return true;
  }

  const octets = normalized.split(".").map((part) => Number(part));
  if (octets.length !== 4 || octets.some((part) => !Number.isInteger(part))) {
    return false;
  }
  return (
    octets[0] === 10 ||
    (octets[0] === 192 && octets[1] === 168) ||
    (octets[0] === 172 && octets[1] >= 16 && octets[1] <= 31)
  );
}

export function buildClinicalHubPreflight(apiBaseUrl: string): ClinicalHubPreflightResult {
  const normalizedBaseUrl = buildBaseUrl(apiBaseUrl);
  const expectedRegion = APP_DATA_RESIDENCY_REGION;
  const baseResult = {
    normalizedBaseUrl,
    expectedRegion,
    inferredRegion: null,
  };

  if (!normalizedBaseUrl) {
    return {
      ...baseResult,
      status: "blocked",
      code: "missing_url",
      message: buildMissingApiBaseUrlMessage(),
    };
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(normalizedBaseUrl);
  } catch {
    return {
      ...baseResult,
      status: "blocked",
      code: "unsupported_url",
      message: "Clinical Hub API Base URL must include http:// or https://.",
    };
  }

  if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") {
    return {
      ...baseResult,
      status: "blocked",
      code: "unsupported_url",
      message: "Clinical Hub API Base URL must use http:// or https://.",
    };
  }

  const hostname = parsedUrl.hostname;
  const inferredRegion = inferClinicalHubRegionFromHostname(hostname);
  const policyRequiresRegionMatch =
    APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB && !APP_ALLOW_CROSS_REGION_SYNC;
  const withRegion = {
    ...baseResult,
    inferredRegion,
  };

  if (
    policyRequiresRegionMatch &&
    inferredRegion != null &&
    inferredRegion !== expectedRegion
  ) {
    return {
      ...withRegion,
      status: "blocked",
      code: "region_mismatch",
      message:
        `Clinical Hub region mismatch: app policy requires ${expectedRegion}, ` +
        `URL appears to target ${inferredRegion}.`,
    };
  }

  if (isLocalClinicalHubHostname(hostname)) {
    return {
      ...withRegion,
      status: "warning",
      code: "local_dev",
      message:
        "Clinical Hub preflight warning: local/LAN URL is allowed for smoke testing only, not live release.",
    };
  }

  if (parsedUrl.protocol !== "https:") {
    return {
      ...withRegion,
      status: "warning",
      code: "insecure_transport",
      message:
        "Clinical Hub preflight warning: use https:// for live pilot sync outside local smoke tests.",
    };
  }

  if (policyRequiresRegionMatch && inferredRegion == null) {
    return {
      ...withRegion,
      status: "warning",
      code: "region_unknown",
      message:
        `Clinical Hub preflight warning: URL region is not obvious; confirm it is ${expectedRegion} before live pilot sync.`,
    };
  }

  return {
    ...withRegion,
    status: "pass",
    code: "configured",
    message: `Clinical Hub preflight OK for ${expectedRegion} region policy.`,
  };
}

export function isClinicalHubPreflightActionAllowed(
  preflight: ClinicalHubPreflightResult,
): boolean {
  return preflight.status !== "blocked";
}
