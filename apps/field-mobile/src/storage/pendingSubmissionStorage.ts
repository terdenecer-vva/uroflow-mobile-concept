import type { PendingSubmission, RequestHeaderContext } from "../types";
import {
  buildHeaderContextFromValues,
  createPendingId,
  normalizePendingEndpoint,
} from "../utils/appHelpers";

type SessionContext = {
  site_id: string;
  operator_id: string;
};

function readString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function extractSessionContext(payload: unknown): SessionContext | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const session = (payload as { session?: unknown }).session;
  if (!session || typeof session !== "object") {
    return null;
  }
  const candidate = session as Record<string, unknown>;
  return {
    site_id: readString(candidate.site_id),
    operator_id: readString(candidate.operator_id),
  };
}

export function normalizeRequestHeaderContext(
  raw: unknown,
  sessionContext: SessionContext,
): RequestHeaderContext {
  if (!raw || typeof raw !== "object") {
    return buildHeaderContextFromValues(
      "",
      "operator",
      sessionContext.site_id,
      sessionContext.operator_id,
    );
  }
  const candidate = raw as Record<string, unknown>;
  return buildHeaderContextFromValues(
    readString(candidate.api_key),
    readString(candidate.actor_role) || "operator",
    readString(candidate.site_id) || sessionContext.site_id,
    readString(candidate.operator_id) || sessionContext.operator_id,
    readString(candidate.request_id),
  );
}

export function normalizePendingSubmission(
  raw: unknown,
  options: {
    createId?: () => string;
    nowIso?: () => string;
  } = {},
): PendingSubmission | null {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const candidate = raw as Record<string, unknown>;
  const payload = candidate.payload;
  const sessionContext = extractSessionContext(payload);
  if (!sessionContext) {
    return null;
  }

  const createId = options.createId ?? createPendingId;
  const nowIso = options.nowIso ?? (() => new Date().toISOString());
  const id = readString(candidate.id).trim() || createId();
  const createdAt = readString(candidate.created_at).trim() || nowIso();
  const attemptCountRaw = Number(candidate.attempt_count);
  const attemptCount = Number.isFinite(attemptCountRaw)
    ? Math.max(0, Math.round(attemptCountRaw))
    : 0;

  return {
    id,
    created_at: createdAt,
    endpoint: normalizePendingEndpoint(candidate.endpoint),
    payload: payload as PendingSubmission["payload"],
    request_headers: normalizeRequestHeaderContext(candidate.request_headers, sessionContext),
    attempt_count: attemptCount,
    last_attempt_at: readString(candidate.last_attempt_at) || null,
    last_error: readString(candidate.last_error) || null,
    last_status_code:
      typeof candidate.last_status_code === "number" ? candidate.last_status_code : null,
  };
}
