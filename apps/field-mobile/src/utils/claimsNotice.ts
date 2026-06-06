export const PILOT_CLAIMS_NOTICE_TITLE = "Pilot comparison only";

export const PILOT_CLAIMS_NOTICE_BODY =
  "Uroflow Field Capture supports pilot comparison with a reference uroflowmeter. It does not diagnose disease, rule out disease, or recommend treatment.";

export const PILOT_CLAIMS_NOTICE_BULLETS = [
  "Review app metrics against the reference uroflowmeter and local clinical SOP before use.",
  "Treat repeat/reject or low-quality captures as collection guidance, not clinical advice.",
  "Escalate care decisions to a qualified clinician; do not rely on this app as a standalone decision tool.",
] as const;

export const REQUIRED_CLAIMS_NOTICE_PHRASES = [
  "pilot comparison",
  "reference uroflowmeter",
  "does not diagnose",
  "rule out disease",
  "recommend treatment",
  "qualified clinician",
  "standalone decision tool",
] as const;

export const BLOCKED_DIAGNOSTIC_CLAIMS = [
  "diagnoses disease",
  "rules out disease",
  "recommends treatment",
  "replaces clinician",
  "standalone diagnostic",
] as const;

export type ClaimsNoticeValidation = {
  status: "pass" | "fail";
  missingRequiredPhrases: string[];
  blockedClaims: string[];
};

export function buildClaimsNoticeText(): string {
  return [
    PILOT_CLAIMS_NOTICE_TITLE,
    PILOT_CLAIMS_NOTICE_BODY,
    ...PILOT_CLAIMS_NOTICE_BULLETS,
  ].join(" ");
}

export function validateClaimsNoticeText(text: string): ClaimsNoticeValidation {
  const normalized = text.toLowerCase();
  const missingRequiredPhrases = REQUIRED_CLAIMS_NOTICE_PHRASES.filter(
    (phrase) => !normalized.includes(phrase),
  );
  const blockedClaims = BLOCKED_DIAGNOSTIC_CLAIMS.filter((claim) =>
    normalized.includes(claim),
  );

  return {
    status:
      missingRequiredPhrases.length === 0 && blockedClaims.length === 0
        ? "pass"
        : "fail",
    missingRequiredPhrases,
    blockedClaims,
  };
}
