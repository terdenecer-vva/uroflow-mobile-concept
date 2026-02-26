from __future__ import annotations

from uroflow_mobile.gate_profile import (
    CLINICAL_FIELD_ALIASES,
    build_profile_template,
    suggest_column_map,
)


def test_suggest_column_map_matches_alias_headers() -> None:
    headers = [
        "QMAX_APP",
        "QMAX_REF",
        "QUALITY_STATUS_CODE",
        "FLOW_START_TIME_S",
    ]

    mapping = suggest_column_map(headers, CLINICAL_FIELD_ALIASES)

    assert mapping["QMAX_APP"] == "app_qmax_ml_s"
    assert mapping["QMAX_REF"] == "ref_qmax_ml_s"
    assert mapping["QUALITY_STATUS_CODE"] == "quality_status"
    assert mapping["FLOW_START_TIME_S"] == "app_t_start_s"


def test_build_profile_template_contains_meta_and_value_maps() -> None:
    template = build_profile_template(
        profile_name="clinic_x",
        clinical_headers=["QMAX_APP", "QMAX_REF", "QUALITY_STATUS_CODE"],
        bench_headers=["SCENARIO_NAME", "QMAX_APP", "QMAX_REF"],
    )

    profile = template["profiles"]["clinic_x"]
    assert profile["meta"]["generated_from"]["clinical_headers"]
    assert profile["clinical"]["value_map"]["quality_status"]["1"] == "valid"
    assert profile["bench"]["value_map"]["quality_status"]["3"] == "reject"
