import React, { useMemo } from "react";
import Svg, { Defs, LinearGradient, Path, Stop } from "react-native-svg";

export function Sparkline({
  data,
  color,
  width = 72,
  height = 24,
}: {
  data: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  const { linePath, areaPath, gradientId } = useMemo(() => {
    const safe = data.length > 1 ? data : [0, 1];
    const min = Math.min(...safe);
    const max = Math.max(...safe);
    const range = max - min || 1;
    const points = safe.map((value, index) => {
      const x = (index / (safe.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return { x, y };
    });
    const line = points
      .map((point, index) =>
        `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`
      )
      .join(" ");
    const area = `${line} L${width},${height} L0,${height} Z`;
    const id = `spark-${color.replace(/[^a-z0-9]/gi, "").slice(0, 18)}`;
    return { linePath: line, areaPath: area, gradientId: id };
  }, [color, data, height, width]);

  return (
    <Svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <Defs>
        <LinearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <Stop offset="100%" stopColor={color} stopOpacity={0} />
        </LinearGradient>
      </Defs>
      <Path d={areaPath} fill={`url(#${gradientId})`} />
      <Path d={linePath} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

