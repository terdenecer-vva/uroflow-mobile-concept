import type {
  EndpointPayload,
  PendingEndpoint,
  RequestHeaderContext,
  SubmitAttemptResult,
} from "../types";
import { clampTimeoutMs, classifyRetryable, createRequestId } from "../utils/appHelpers";

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
  if (endpoint === "capture_packages") {
    return "/api/v1/capture-packages";
  }
  return "/api/v1/paired-measurements";
}

export function buildRequestHeaders(
  includeContentType: boolean,
  headerContext: RequestHeaderContext,
): Record<string, string> {
  const headers: Record<string, string> = {};
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
      retryable: !response.ok ? classifyRetryable(response.status) : false,
    };
  } catch (error) {
    return {
      ok: false,
      statusCode: null,
      body: String(error),
      retryable: true,
    };
  }
}
