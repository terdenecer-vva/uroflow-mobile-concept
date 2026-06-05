import type {
  EndpointPayload,
  PendingEndpoint,
  RequestHeaderContext,
  SubmitAttemptResult,
} from "../types";
import {
  APP_DATA_RESIDENCY_BOUNDARY,
  APP_DATA_RESIDENCY_REGION,
  APP_ENDPOINT_PATHS,
  APP_ENDPOINT_SET,
  APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB,
  APP_RUNTIME_MODE,
} from "../config/appConfig";
import {
  APP_CAPTURE_SCHEMA_VERSION,
  APP_MODEL_ID,
  APP_RELEASE_VERSION,
} from "../config/releaseMetadata";
import {
  clampTimeoutMs,
  classifyEndpointRetryable,
  createRequestId,
  summarizeSafeExceptionCategory,
} from "../utils/appHelpers";

export function buildBaseUrl(apiBaseUrl: string): string {
  return apiBaseUrl.trim().replace(/\/+$/, "");
}

export function isConfiguredApiBaseUrl(apiBaseUrl: string): boolean {
  return /^https?:\/\//i.test(buildBaseUrl(apiBaseUrl));
}

export function buildMissingApiBaseUrlMessage(): string {
  return "Configure Clinical Hub API Base URL before testing, submitting, or syncing.";
}

export function endpointPath(endpoint: PendingEndpoint): string {
  return APP_ENDPOINT_PATHS[endpoint];
}

export function buildRuntimeTraceHeaders(): Record<string, string> {
  return {
    "x-uroflow-app-version": APP_RELEASE_VERSION,
    "x-uroflow-model-id": APP_MODEL_ID,
    "x-uroflow-capture-schema-version": APP_CAPTURE_SCHEMA_VERSION,
    "x-uroflow-runtime-mode": APP_RUNTIME_MODE,
    "x-uroflow-endpoint-set": APP_ENDPOINT_SET,
    "x-uroflow-data-residency-region": APP_DATA_RESIDENCY_REGION,
    "x-uroflow-data-residency-boundary": APP_DATA_RESIDENCY_BOUNDARY,
    "x-uroflow-region-match-required": String(APP_REQUIRE_REGION_MATCHED_CLINICAL_HUB),
  };
}

export function buildRequestHeaders(
  includeContentType: boolean,
  headerContext: RequestHeaderContext,
): Record<string, string> {
  const headers: Record<string, string> = buildRuntimeTraceHeaders();
  if (includeContentType) {
    headers["Content-Type"] = "application/json";
  }
  if (headerContext.api_key) {
    headers["x-api-key"] = headerContext.api_key;
  }
  if (headerContext.operator_id) {
    headers["x-operator-id"] = headerContext.operator_id;
  }
  if (headerContext.site_id) {
    headers["x-site-id"] = headerContext.site_id;
  }
  if (headerContext.actor_role) {
    headers["x-actor-role"] = headerContext.actor_role;
  }
  headers["x-request-id"] = headerContext.request_id?.trim() || createRequestId();
  return headers;
}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  requestTimeoutMs: string,
): Promise<Response> {
  const timeoutMs = clampTimeoutMs(requestTimeoutMs);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}

export async function attemptSubmitEndpoint(options: {
  apiBaseUrl: string;
  requestTimeoutMs: string;
  endpoint: PendingEndpoint;
  endpointPayload: EndpointPayload;
  headerContext: RequestHeaderContext;
}): Promise<SubmitAttemptResult> {
  const url = `${buildBaseUrl(options.apiBaseUrl)}${endpointPath(options.endpoint)}`;
  try {
    const response = await fetchWithTimeout(
      url,
      {
        method: "POST",
        headers: buildRequestHeaders(true, options.headerContext),
        body: JSON.stringify(options.endpointPayload),
      },
      options.requestTimeoutMs,
    );
    const body = await response.text();
    return {
      ok: response.ok,
      statusCode: response.status,
      body,
      retryable: !response.ok
        ? classifyEndpointRetryable(options.endpoint, response.status)
        : false,
    };
  } catch (error) {
    return {
      ok: false,
      statusCode: null,
      body: summarizeSafeExceptionCategory(error, "network_or_timeout"),
      retryable: true,
    };
  }
}
