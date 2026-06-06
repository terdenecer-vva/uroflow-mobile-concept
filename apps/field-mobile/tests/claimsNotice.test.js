const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const buildDir = process.env.MOBILE_UNIT_BUILD_DIR ?? "/tmp/uroflow-field-mobile-unit";
const claimsNotice = require(path.join(buildDir, "utils/claimsNotice.js"));

test("pilot claims notice keeps comparison-only and non-diagnostic wording", () => {
  const text = claimsNotice.buildClaimsNoticeText();
  const validation = claimsNotice.validateClaimsNoticeText(text);

  assert.equal(claimsNotice.PILOT_CLAIMS_NOTICE_TITLE, "Pilot comparison only");
  assert.match(text, /reference uroflowmeter/i);
  assert.match(text, /does not diagnose/i);
  assert.match(text, /recommend treatment/i);
  assert.match(text, /qualified clinician/i);
  assert.equal(validation.status, "pass");
  assert.deepEqual(validation.missingRequiredPhrases, []);
  assert.deepEqual(validation.blockedClaims, []);
});

test("claims notice validator flags missing safeguards and over-claim language", () => {
  const validation = claimsNotice.validateClaimsNoticeText(
    "This app diagnoses disease and replaces clinician review.",
  );

  assert.equal(validation.status, "fail");
  assert.ok(validation.missingRequiredPhrases.includes("pilot comparison"));
  assert.ok(validation.blockedClaims.includes("diagnoses disease"));
  assert.ok(validation.blockedClaims.includes("replaces clinician"));
});
