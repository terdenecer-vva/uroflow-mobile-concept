import type { AuthContextResponse } from "../types";
import { buildBaseUrl } from "./clinicalHub";

export function buildAuthContextUrl(apiBaseUrl: string): string {
  return `${buildBaseUrl(apiBaseUrl)}/api/v1/auth-context`;
}

export function buildHealthUrl(apiBaseUrl: string): string {
  return `${buildBaseUrl(apiBaseUrl)}/health`;
}

export function buildHealthCheckFailedMessage(status: number): string {
  return `Health check failed: HTTP ${status}`;
}

export function buildAuthContextCheckFailedMessage(
  status: number,
  body: string,
): string {
  return `Auth-context check failed: HTTP ${status} ${body}`;
}

export function buildAuthContextOkMessage(
  authContext: AuthContextResponse,
): string {
  return (
    `Auth context OK: auth=${authContext.auth_result}, ` +
    `role=${authContext.actor_role ?? "n/a"}, ` +
    `site=${authContext.actor_site_id ?? "n/a"}`
  );
}

export function buildApiCheckFailedMessage(error: unknown): string {
  return `API check failed: ${String(error)}`;
}
