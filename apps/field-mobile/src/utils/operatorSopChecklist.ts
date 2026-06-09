export type OperatorSopChecklistKey =
  | "reference_uroflowmeter_ready"
  | "phone_stable"
  | "water_impact_sop_confirmed"
  | "metadata_privacy_checked";

export type OperatorSopChecklistItem = {
  key: OperatorSopChecklistKey;
  label: string;
  evidenceHint: string;
};

export type OperatorSopChecklistState = Record<OperatorSopChecklistKey, boolean>;

export type OperatorSopReadiness = {
  ready: boolean;
  missingKeys: OperatorSopChecklistKey[];
  message: string;
};

export const OPERATOR_SOP_CHECKLIST_ITEMS: OperatorSopChecklistItem[] = [
  {
    key: "reference_uroflowmeter_ready",
    label: "Reference uroflowmeter ready",
    evidenceHint: "Reference device is zeroed/ready and the paired attempt is aligned.",
  },
  {
    key: "phone_stable",
    label: "Phone stable and hands clear",
    evidenceHint: "Phone is fixed in the SOP position before the void starts.",
  },
  {
    key: "water_impact_sop_confirmed",
    label: "Water-impact SOP confirmed",
    evidenceHint: "Stream is aimed at water; wall/floor fallback modes are not used.",
  },
  {
    key: "metadata_privacy_checked",
    label: "Metadata and privacy checked",
    evidenceHint: "Site/operator/session metadata is correct and raw media is not retained.",
  },
];

export const DEFAULT_OPERATOR_SOP_CHECKLIST: OperatorSopChecklistState =
  OPERATOR_SOP_CHECKLIST_ITEMS.reduce<OperatorSopChecklistState>(
    (acc, item) => {
      acc[item.key] = false;
      return acc;
    },
    {
      reference_uroflowmeter_ready: false,
      phone_stable: false,
      water_impact_sop_confirmed: false,
      metadata_privacy_checked: false,
    },
  );

export function buildOperatorSopReadiness(
  checklist: OperatorSopChecklistState,
): OperatorSopReadiness {
  const missingKeys = OPERATOR_SOP_CHECKLIST_ITEMS.filter(
    (item) => checklist[item.key] !== true,
  ).map((item) => item.key);

  if (missingKeys.length > 0) {
    const missingLabels = OPERATOR_SOP_CHECKLIST_ITEMS.filter((item) =>
      missingKeys.includes(item.key),
    ).map((item) => item.label);
    return {
      ready: false,
      missingKeys,
      message: `Confirm operator SOP checklist before capture: ${missingLabels.join(", ")}.`,
    };
  }

  return {
    ready: true,
    missingKeys: [],
    message: "Operator SOP checklist confirmed.",
  };
}

export function toggleOperatorSopChecklistItem(
  checklist: OperatorSopChecklistState,
  key: OperatorSopChecklistKey,
): OperatorSopChecklistState {
  return {
    ...checklist,
    [key]: !checklist[key],
  };
}
