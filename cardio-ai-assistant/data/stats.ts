
export interface StatMetric {
  label: string;
  value: string;
  trend?: string; // e.g., "+10%"
  trendDirection?: 'up' | 'down' | 'neutral';
}

export interface ChartDataPoint {
  name: string;
  value: number;
}

export interface FrequencyDataPoint {
  day: string;
  val: number;
}

export interface StatsPeriodData {
  volumeData: ChartDataPoint[];
  frequencyData: FrequencyDataPoint[];
  metrics: StatMetric[];
  volumeTitle: string;
  frequencyTitle: string;
}

export const statsData: Record<'Week' | 'Month' | 'Year' | 'All-Time', StatsPeriodData> = {
  'Week': {
    volumeTitle: 'This Week\'s Volume',
    frequencyTitle: 'Daily Activity',
    volumeData: [
      { name: 'Mon', value: 45 },
      { name: 'Tue', value: 30 },
      { name: 'Wed', value: 60 },
      { name: 'Thu', value: 0 },
      { name: 'Fri', value: 45 },
      { name: 'Sat', value: 90 },
      { name: 'Sun', value: 30 },
    ],
    frequencyData: [
      { day: 'M', val: 80 },
      { day: 'T', val: 50 },
      { day: 'W', val: 90 },
      { day: 'T', val: 0 },
      { day: 'F', val: 60 },
      { day: 'S', val: 100 },
      { day: 'S', val: 40 },
    ],
    metrics: [
      { label: 'Total Duration', value: '300 min', trend: '+5%', trendDirection: 'up' },
      { label: 'Workouts', value: '6', trend: 'On Track', trendDirection: 'neutral' },
      { label: 'Calories', value: '2,100', trend: '+150', trendDirection: 'up' },
      { label: 'Avg HR', value: '135 bpm', trend: '-2 bpm', trendDirection: 'down' }
    ]
  },
  'Month': {
    volumeTitle: 'Monthly Volume',
    frequencyTitle: 'Weekly Frequency',
    volumeData: [
      { name: 'W1', value: 1200 },
      { name: 'W2', value: 1350 },
      { name: 'W3', value: 1100 },
      { name: 'W4', value: 1500 },
    ],
    frequencyData: [
      { day: 'W1', val: 4 },
      { day: 'W2', val: 5 },
      { day: 'W3', val: 3 },
      { day: 'W4', val: 6 },
    ],
    metrics: [
      { label: 'Total Duration', value: '5,150 min', trend: '+12%', trendDirection: 'up' },
      { label: 'Workouts', value: '18', trend: '+2', trendDirection: 'up' },
      { label: 'Calories', value: '15,400', trend: '+8%', trendDirection: 'up' },
      { label: 'Avg HR', value: '138 bpm', trend: 'Stable', trendDirection: 'neutral' }
    ]
  },
  'Year': {
    volumeTitle: 'Yearly Overview',
    frequencyTitle: 'Monthly Consistency',
    volumeData: [
      { name: 'Jan', value: 4000 },
      { name: 'Feb', value: 3500 },
      { name: 'Mar', value: 5000 },
      { name: 'Apr', value: 4800 },
      { name: 'May', value: 5200 },
      { name: 'Jun', value: 4900 },
    ],
    frequencyData: [
      { day: 'J', val: 15 },
      { day: 'F', val: 12 },
      { day: 'M', val: 20 },
      { day: 'A', val: 18 },
      { day: 'M', val: 22 },
      { day: 'J', val: 19 },
    ],
    metrics: [
      { label: 'Total Duration', value: '27,400 min', trend: '+25%', trendDirection: 'up' },
      { label: 'Workouts', value: '106', trend: 'Consistent', trendDirection: 'up' },
      { label: 'Calories', value: '180k', trend: '---', trendDirection: 'neutral' },
      { label: 'Avg HR', value: '140 bpm', trend: '-5 bpm', trendDirection: 'down' }
    ]
  },
  'All-Time': {
    volumeTitle: 'Lifetime Volume',
    frequencyTitle: 'Activity Distribution',
    volumeData: [
      { name: '2022', value: 30000 },
      { name: '2023', value: 45000 },
      { name: '2024', value: 27400 },
    ],
    frequencyData: [
      { day: 'Mon', val: 45 },
      { day: 'Tue', val: 30 },
      { day: 'Wed', val: 55 },
      { day: 'Thu', val: 35 },
      { day: 'Fri', val: 40 },
      { day: 'Sat', val: 60 },
      { day: 'Sun', val: 25 },
    ],
    metrics: [
      { label: 'Total Duration', value: '102k min', trend: '', trendDirection: 'neutral' },
      { label: 'Workouts', value: '452', trend: '', trendDirection: 'neutral' },
      { label: 'Calories', value: '850k', trend: '', trendDirection: 'neutral' },
      { label: 'Avg HR', value: '142 bpm', trend: '', trendDirection: 'neutral' }
    ]
  }
};

export const personalBestsData = [
  { icon: 'directions_run', title: 'Longest Run', date: 'May 12, 2024', value: '10.2 km', color: 'text-amber-400 bg-amber-400/20' },
  { icon: 'fitness_center', title: 'Heaviest Deadlift', date: 'May 15, 2024', value: '120 kg', color: 'text-rose-400 bg-rose-400/20' },
  { icon: 'timer', title: 'Longest Workout', date: 'May 9, 2024', value: '95 min', color: 'text-sky-400 bg-sky-400/20' },
  { icon: 'bolt', title: 'Max Heart Rate', date: 'Apr 20, 2024', value: '178 bpm', color: 'text-purple-400 bg-purple-400/20' }
];
