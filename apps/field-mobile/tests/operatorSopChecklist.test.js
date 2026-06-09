const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const sop = require(path.join(buildDir, "utils/operatorSopChecklist.js"));

test("operator SOP checklist blocks capture until every item is confirmed", () => {
  const readiness = sop.buildOperatorSopReadiness(sop.DEFAULT_OPERATOR_SOP_CHECKLIST);

  assert.equal(readiness.ready, false);
  assert.deepEqual(readiness.missingKeys, [
    "reference_uroflowmeter_ready",
    "phone_stable",
    "water_impact_sop_confirmed",
    "metadata_privacy_checked",
  ]);
  assert.match(readiness.message, /Reference uroflowmeter ready/);
  assert.match(readiness.message, /Metadata and privacy checked/);
});

test("operator SOP checklist passes after all required confirmations", () => {
  const complete = {
    reference_uroflowmeter_ready: true,
    phone_stable: true,
    water_impact_sop_confirmed: true,
    metadata_privacy_checked: true,
  };

  assert.deepEqual(sop.buildOperatorSopReadiness(complete), {
    ready: true,
    missingKeys: [],
    message: "Operator SOP checklist confirmed.",
  });
});

test("toggleOperatorSopChecklistItem updates one checklist item immutably", () => {
  const updated = sop.toggleOperatorSopChecklistItem(
    sop.DEFAULT_OPERATOR_SOP_CHECKLIST,
    "phone_stable",
  );

  assert.equal(sop.DEFAULT_OPERATOR_SOP_CHECKLIST.phone_stable, false);
  assert.equal(updated.phone_stable, true);
  assert.equal(updated.reference_uroflowmeter_ready, false);
});
