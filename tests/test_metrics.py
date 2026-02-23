from uroflow_mobile.metrics import calculate_uroflow_summary


def test_calculate_uroflow_summary_basic_curve() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0]
    flow = [0.0, 5.0, 10.0, 5.0, 0.0]

    summary = calculate_uroflow_summary(timestamps, flow)

    assert summary.voiding_time_s == 4.0
    assert summary.q_max_ml_s == 10.0
    assert summary.time_to_qmax_s == 2.0
    assert abs(summary.voided_volume_ml - 20.0) < 1e-9
    assert abs(summary.flow_time_s - 4.0) < 1e-9
    assert abs(summary.q_avg_ml_s - 5.0) < 1e-9


def test_interruptions_counted_only_for_internal_pauses() -> None:
    timestamps = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    flow = [0.0, 6.0, 0.0, 0.0, 5.0, 0.0, 0.0]

    summary = calculate_uroflow_summary(timestamps, flow, threshold_ml_s=0.5, min_pause_s=1.0)

    assert summary.interruptions_count == 1
