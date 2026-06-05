const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const summary = require(path.join(buildDir, "api/summaryRequests.js"));

test("buildComparisonSummaryUrl includes trimmed site, sync, and quality filters", () => {
  assert.equal(
    summary.buildComparisonSummaryUrl({
      apiBaseUrl: "https://clinical.example.test/",
      siteId: " SITE-001 ",
      summarySyncId: " SYNC-001 ",
      summaryQualityStatus: "repeat",
    }),
    "https://clinical.example.test/api/v1/comparison-summary?site_id=SITE-001&sync_id=SYNC-001&quality_status=repeat",
  );
});

test("buildCaptureCoverageSummaryUrl omits blank optional filters", () => {
  assert.equal(
    summary.buildCaptureCoverageSummaryUrl({
      apiBaseUrl: "https://clinical.example.test",
      siteId: " ",
      summarySyncId: "",
      summaryQualityStatus: "all",
    }),
    "https://clinical.example.test/api/v1/capture-coverage-summary?quality_status=all",
  );
});

test("summary URL builders encode filter values", () => {
  const url = summary.buildComparisonSummaryUrl({
    apiBaseUrl: "https://clinical.example.test",
    siteId: "SITE 1",
    summarySyncId: "SYNC/001",
    summaryQualityStatus: "valid",
  });

  assert.equal(
    url,
    "https://clinical.example.test/api/v1/comparison-summary?site_id=SITE+1&sync_id=SYNC%2F001&quality_status=valid",
  );
});
