from uroflow_mobile.metrics import calculate_uroflow_summary


def main() -> None:
    timestamps = [
        0.0,
        0.5,
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
        3.5,
        4.0,
        4.5,
        5.0,
    ]
    flow = [0.0, 2.0, 6.0, 10.0, 12.0, 11.0, 9.0, 6.0, 3.0, 1.0, 0.0]

    summary = calculate_uroflow_summary(timestamps, flow)

    print("Uroflow summary")
    print(f"Voided volume: {summary.voided_volume_ml:.2f} ml")
    print(f"Qmax: {summary.q_max_ml_s:.2f} ml/s")
    print(f"Qavg: {summary.q_avg_ml_s:.2f} ml/s")
    print(f"Voiding time: {summary.voiding_time_s:.2f} s")
    print(f"Flow time: {summary.flow_time_s:.2f} s")
    print(f"Time to Qmax: {summary.time_to_qmax_s:.2f} s")
    print(f"Interruptions: {summary.interruptions_count}")


if __name__ == "__main__":
    main()
