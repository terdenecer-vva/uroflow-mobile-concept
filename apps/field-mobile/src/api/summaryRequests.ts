import type { SummaryQualityStatus } from "../types";
import { buildBaseUrl } from "./clinicalHub";

type SummaryUrlOptions = {
  apiBaseUrl: string;
  siteId: string;
  summarySyncId: string;
  summaryQualityStatus: SummaryQualityStatus;
};

function buildSummaryQuery(options: SummaryUrlOptions): string {
  const params = new URLSearchParams();
  const siteId = options.siteId.trim();
  const syncId = options.summarySyncId.trim();
  if (siteId) {
    params.set("site_id", siteId);
  }
  if (syncId) {
    params.set("sync_id", syncId);
  }
  params.set("quality_status", options.summaryQualityStatus);
  return params.toString();
}

export function buildComparisonSummaryUrl(options: SummaryUrlOptions): string {
  return `${buildBaseUrl(options.apiBaseUrl)}/api/v1/comparison-summary?${buildSummaryQuery(
    options,
  )}`;
}

export function buildCaptureCoverageSummaryUrl(options: SummaryUrlOptions): string {
  return `${buildBaseUrl(
    options.apiBaseUrl,
  )}/api/v1/capture-coverage-summary?${buildSummaryQuery(options)}`;
}
