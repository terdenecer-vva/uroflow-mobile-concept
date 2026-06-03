import React, { useMemo } from "react";
import { Text, View } from "react-native";

import type { RuntimeFlowPoint } from "../capture/runtimeCaptureSession";
import { styles } from "../styles/appStyles";

type RuntimeCurvePreviewProps = {
  flowSeries: RuntimeFlowPoint[];
};

function buildPreview(flowSeries: RuntimeFlowPoint[]): RuntimeFlowPoint[] {
  if (flowSeries.length <= 32) {
    return flowSeries;
  }

  const step = Math.ceil(flowSeries.length / 32);
  const selected: RuntimeFlowPoint[] = [];
  for (let index = 0; index < flowSeries.length; index += step) {
    selected.push(flowSeries[index]);
  }
  const lastPoint = flowSeries[flowSeries.length - 1];
  if (selected[selected.length - 1] !== lastPoint) {
    selected.push(lastPoint);
  }
  return selected;
}

function getMaxFlow(points: RuntimeFlowPoint[]): number {
  if (points.length === 0) {
    return 1;
  }
  return Math.max(
    1,
    ...points.map((point) => (Number.isFinite(point.flow_ml_s) ? point.flow_ml_s : 0)),
  );
}

export function RuntimeCurvePreview({ flowSeries }: RuntimeCurvePreviewProps) {
  const preview = useMemo(() => buildPreview(flowSeries), [flowSeries]);
  const maxFlow = useMemo(() => getMaxFlow(preview), [preview]);

  return (
    <View style={styles.curveBox}>
      {preview.length === 0 ? (
        <Text style={styles.responseText}>No runtime curve yet. Run capture and press Stop.</Text>
      ) : (
        preview.map((point, index) => {
          const widthPct = Math.min(100, Math.max(0, (point.flow_ml_s / maxFlow) * 100));
          return (
            <View key={`${point.t_s.toFixed(3)}-${index}`} style={styles.curveRow}>
              <Text style={styles.curveTimeText}>{point.t_s.toFixed(1)}s</Text>
              <View style={styles.curveBarTrack}>
                <View style={[styles.curveBarFill, { width: `${widthPct}%` }]} />
              </View>
              <Text style={styles.curveValueText}>{point.flow_ml_s.toFixed(1)}</Text>
            </View>
          );
        })
      )}
    </View>
  );
}
