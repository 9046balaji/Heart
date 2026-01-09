/**
 * Memoized Chart Components
 *
 * Performance-optimized chart components to prevent unnecessary re-renders.
 * These components are designed for use in Dashboard and other screens
 * where charts might re-render frequently due to state changes.
 */

import React, { memo, useMemo, useCallback } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Brush,
  LineChart,
  Line,
  BarChart,
  Bar,
  CartesianGrid,
  Legend
} from 'recharts';

// ============================================================================
// Types
// ============================================================================

export interface ChartDataPoint {
  [key: string]: string | number | undefined;
}

export interface HeartRateChartProps {
  data: ChartDataPoint[];
  onPointClick?: (data: ChartDataPoint) => void;
  isCaretakerMode?: boolean;
  isLive?: boolean;
  className?: string;
}

export interface VitalsChartProps {
  data: ChartDataPoint[];
  dataKey: string;
  color?: string;
  gradientId?: string;
  onPointClick?: (data: ChartDataPoint) => void;
  showBrush?: boolean;
  className?: string;
}

export interface StepsChartProps {
  data: ChartDataPoint[];
  goal?: number;
  className?: string;
}

// ============================================================================
// Custom Tooltip Component
// ============================================================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number; dataKey: string; color?: string }>;
  label?: string;
  unit?: string;
}

const CustomChartTooltip: React.FC<CustomTooltipProps> = memo(({
  active,
  payload,
  label,
  unit = ''
}) => {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="bg-slate-800 dark:bg-slate-900 px-3 py-2 rounded-lg shadow-lg border border-slate-700">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-sm font-semibold text-white">
          {entry.value}{unit}
        </p>
      ))}
    </div>
  );
});

CustomChartTooltip.displayName = 'CustomChartTooltip';

// ============================================================================
// Memoized Heart Rate Chart
// ============================================================================

/**
 * Optimized heart rate chart component
 * Memoized to prevent re-renders when parent state changes
 */
export const MemoizedHeartRateChart = memo<HeartRateChartProps>(({
  data,
  onPointClick,
  isCaretakerMode = false,
  isLive = false,
  className = ''
}) => {
  // Memoize color values
  const colors = useMemo(() => ({
    stroke: isCaretakerMode ? "#ef4444" : "#137fec",
    gradientStart: isCaretakerMode ? "#ef4444" : "#137fec",
    cursor: isCaretakerMode ? "#ef4444" : "#137fec"
  }), [isCaretakerMode]);

  // Memoize click handler
  const handleClick = useCallback((chartData: any) => {
    if (chartData?.activePayload?.[0]?.payload && onPointClick) {
      onPointClick(chartData.activePayload[0].payload);
    }
  }, [onPointClick]);

  // Memoize gradient ID to prevent recreation
  const gradientId = useMemo(() =>
    `heartRateGradient-${isCaretakerMode ? 'caretaker' : 'normal'}`,
    [isCaretakerMode]
  );

  return (
    <div className={`w-full ${className}`}>
      <ResponsiveContainer width="100%" height={150} minWidth={0} minHeight={0} debounce={50}>
        <AreaChart data={data} onClick={handleClick}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={colors.gradientStart} stopOpacity={0.3} />
              <stop offset="95%" stopColor={colors.gradientStart} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Tooltip
            content={<CustomChartTooltip unit=" bpm" />}
            cursor={{ stroke: colors.cursor, strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="bpm"
            stroke={colors.stroke}
            strokeWidth={3}
            fillOpacity={1}
            fill={`url(#${gradientId})`}
            activeDot={{ r: 6 }}
            isAnimationActive={!isLive} // Disable animation for live data
          />
          <XAxis
            dataKey="day"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#64748b' }}
            interval={0}
          />
          <Brush
            dataKey="day"
            height={20}
            stroke="#334155"
            fill="#1e293b"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}, (prevProps, nextProps) => {
  // Custom comparison - only re-render if these specific props change
  return (
    prevProps.isCaretakerMode === nextProps.isCaretakerMode &&
    prevProps.isLive === nextProps.isLive &&
    prevProps.data === nextProps.data &&
    prevProps.onPointClick === nextProps.onPointClick
  );
});

MemoizedHeartRateChart.displayName = 'MemoizedHeartRateChart';

// ============================================================================
// Memoized Vitals Chart (Generic)
// ============================================================================

/**
 * Generic vitals chart that can display any numeric metric
 */
export const MemoizedVitalsChart = memo<VitalsChartProps>(({
  data,
  dataKey,
  color = '#137fec',
  gradientId = 'vitalsGradient',
  onPointClick,
  showBrush = false,
  className = ''
}) => {
  const handleClick = useCallback((chartData: any) => {
    if (chartData?.activePayload?.[0]?.payload && onPointClick) {
      onPointClick(chartData.activePayload[0].payload);
    }
  }, [onPointClick]);

  return (
    <div className={`w-full ${className}`}>
      <ResponsiveContainer width="100%" height={150} debounce={50}>
        <AreaChart data={data} onClick={handleClick}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Tooltip content={<CustomChartTooltip />} />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            fillOpacity={1}
            fill={`url(#${gradientId})`}
            activeDot={{ r: 5 }}
          />
          <XAxis
            dataKey="day"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#64748b' }}
          />
          {showBrush && (
            <Brush dataKey="day" height={20} stroke="#334155" fill="#1e293b" />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
});

MemoizedVitalsChart.displayName = 'MemoizedVitalsChart';

// ============================================================================
// Memoized Steps Bar Chart
// ============================================================================

/**
 * Bar chart for daily step counts with optional goal line
 */
export const MemoizedStepsChart = memo<StepsChartProps>(({
  data,
  goal = 10000,
  className = ''
}) => {
  // Memoize processed data with goal comparison
  const processedData = useMemo(() =>
    data.map(d => ({
      ...d,
      goalMet: (d.steps as number || 0) >= goal
    })),
    [data, goal]
  );

  return (
    <div className={`w-full ${className}`}>
      <ResponsiveContainer width="100%" height={150} debounce={50}>
        <BarChart data={processedData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
          <XAxis
            dataKey="day"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#64748b' }}
          />
          <YAxis hide domain={[0, 'auto']} />
          <Tooltip content={<CustomChartTooltip unit=" steps" />} />
          <Bar
            dataKey="steps"
            radius={[4, 4, 0, 0]}
            fill="#137fec"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
});

MemoizedStepsChart.displayName = 'MemoizedStepsChart';

// ============================================================================
// Memoized Blood Pressure Chart
// ============================================================================

export interface BloodPressureData {
  day: string;
  systolic: number;
  diastolic: number;
}

export interface BloodPressureChartProps {
  data: BloodPressureData[];
  className?: string;
}

export const MemoizedBloodPressureChart = memo<BloodPressureChartProps>(({
  data,
  className = ''
}) => {
  return (
    <div className={`w-full ${className}`}>
      <ResponsiveContainer width="100%" height={180} debounce={50}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="day"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#64748b' }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 10, fill: '#64748b' }}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1e293b',
              border: 'none',
              borderRadius: '8px',
              fontSize: '12px'
            }}
            itemStyle={{ color: '#fff' }}
          />
          <Legend
            iconType="line"
            wrapperStyle={{ fontSize: '10px' }}
          />
          <Line
            type="monotone"
            dataKey="systolic"
            stroke="#ef4444"
            strokeWidth={2}
            dot={{ r: 3 }}
            name="Systolic"
          />
          <Line
            type="monotone"
            dataKey="diastolic"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3 }}
            name="Diastolic"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
});

MemoizedBloodPressureChart.displayName = 'MemoizedBloodPressureChart';

// ============================================================================
// Export all charts
// ============================================================================

export default {
  HeartRateChart: MemoizedHeartRateChart,
  VitalsChart: MemoizedVitalsChart,
  StepsChart: MemoizedStepsChart,
  BloodPressureChart: MemoizedBloodPressureChart,
};
