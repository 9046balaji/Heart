
import React, { useState } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { statsData, personalBestsData } from '../data/stats';

const StatsScreen: React.FC = () => {
  const [period, setPeriod] = useState<'Week' | 'Month' | 'Year' | 'All-Time'>('Week');
  const data = statsData[period];

  // Simulated streak data
  const currentStreak = 12;
  const longestStreak = 28;
  const weeklyGoalDays = 5;
  const completedDays = 4;
  const weekDays = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
  const completedMap = [true, true, false, true, true, false, false]; // this week

  // Custom tooltip that adapts to theme
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 shadow-lg text-xs">
        <p className="text-slate-500 dark:text-slate-400 mb-0.5">{label}</p>
        <p className="font-bold text-slate-900 dark:text-white">{payload[0].value.toLocaleString()}</p>
      </div>
    );
  };

  return (
    <div className="pb-24 animate-in fade-in slide-in-from-bottom-4 duration-300 px-4 pt-4">
      {/* Period Selector */}
      <div className="flex bg-slate-200 dark:bg-slate-800 p-1 rounded-xl mb-6">
        {['Week', 'Month', 'Year', 'All-Time'].map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p as any)}
            className={`flex-1 py-2 text-xs font-bold rounded-lg transition-all ${
              period === p
                ? 'bg-white dark:bg-card-dark text-slate-900 dark:text-white shadow-sm'
                : 'text-slate-500 dark:text-slate-400'
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Streak & Consistency Widget */}
      <div className="bg-gradient-to-br from-orange-500 to-amber-500 rounded-2xl p-5 mb-6 text-white shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-40 h-40 bg-white/10 rounded-full -mr-16 -mt-16 blur-2xl"></div>
        <div className="flex items-center justify-between mb-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="material-symbols-outlined filled text-2xl">local_fire_department</span>
              <span className="text-3xl font-bold">{currentStreak}</span>
              <span className="text-sm opacity-90">day streak</span>
            </div>
            <p className="text-xs text-white/70">Longest: {longestStreak} days</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-white/70 mb-1">Weekly Goal</p>
            <p className="text-lg font-bold">{completedDays}/{weeklyGoalDays} days</p>
          </div>
        </div>
        {/* Mini week dots */}
        <div className="flex gap-2 justify-center relative z-10">
          {weekDays.map((d, i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                completedMap[i]
                  ? 'bg-white text-orange-600 shadow-sm'
                  : i < new Date().getDay() ? 'bg-white/20 text-white/60' : 'bg-white/10 text-white/40'
              }`}>
                {completedMap[i] ? (
                  <span className="material-symbols-outlined text-sm">check</span>
                ) : d}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="grid grid-cols-2 gap-3 mb-6">
        {data.metrics.map((metric, i) => (
          <div key={i} className="bg-white dark:bg-card-dark p-4 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
            <p className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">{metric.label}</p>
            <div className="flex items-end gap-2">
              <span className="text-xl font-bold dark:text-white">{metric.value}</span>
              {metric.trend && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center ${
                  metric.trendDirection === 'up' ? 'text-green-600 bg-green-100 dark:bg-green-900/30' :
                  metric.trendDirection === 'down' ? 'text-red-600 bg-red-100 dark:bg-red-900/30' :
                  'text-slate-600 bg-slate-100 dark:bg-slate-800'
                }`}>
                  {metric.trendDirection === 'up' && '↑'}
                  {metric.trendDirection === 'down' && '↓'}
                  {metric.trend}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Volume Chart */}
      <div className="bg-white dark:bg-card-dark p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm mb-6">
        <h3 className="font-bold text-lg dark:text-white mb-4">{data.volumeTitle}</h3>
        <div className="h-48 w-full min-w-0 min-h-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
            <AreaChart data={data.volumeData}>
              <defs>
                <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#137fec" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#137fec" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#137fec', strokeWidth: 1 }} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#137fec"
                strokeWidth={3}
                fillOpacity={1}
                fill="url(#colorVolume)"
              />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} dy={10} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Frequency Chart */}
      <div className="bg-white dark:bg-card-dark p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm mb-6">
        <h3 className="font-bold text-lg dark:text-white mb-4">{data.frequencyTitle}</h3>
        <div className="h-40 w-full min-w-0 min-h-0">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
            <BarChart data={data.frequencyData}>
              <Tooltip content={<CustomTooltip />} cursor={{fill: 'transparent'}} />
              <Bar dataKey="val" radius={[6, 6, 6, 6]}>
                {data.frequencyData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.val > 50 ? '#10b981' : '#e2e8f0'} />
                ))}
              </Bar>
              <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} dy={10} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Personal Bests */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-bold text-lg dark:text-white">Personal Records</h3>
          <span className="material-symbols-outlined text-amber-400 filled">emoji_events</span>
        </div>
        <div className="space-y-3">
          {personalBestsData.map((pb, i) => (
            <div key={i} className="flex items-center gap-4 bg-white dark:bg-card-dark p-4 rounded-xl border border-slate-100 dark:border-slate-800 shadow-sm group hover:border-primary/30 transition-all">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${pb.color} transition-transform group-hover:scale-110`}>
                <span className="material-symbols-outlined">{pb.icon}</span>
              </div>
              <div className="flex-1">
                <p className="text-xs text-slate-500 uppercase font-bold tracking-wider">{pb.title}</p>
                <p className="text-lg font-bold dark:text-white">{pb.value}</p>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate-400">{pb.date}</span>
                <div className="mt-1">
                  <span className="material-symbols-outlined text-amber-400 text-sm filled">star</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Weekly Comparison */}
      {period === 'Week' && (
        <div className="mt-6 bg-white dark:bg-card-dark p-5 rounded-2xl border border-slate-100 dark:border-slate-800 shadow-sm">
          <h3 className="font-bold dark:text-white mb-3">vs Last Week</h3>
          <div className="space-y-3">
            {[
              { label: 'Total Duration', current: '300 min', prev: '285 min', pct: '+5%', up: true },
              { label: 'Workouts', current: '6', prev: '5', pct: '+20%', up: true },
              { label: 'Avg Intensity', current: 'Medium', prev: 'Medium', pct: '—', up: false }
            ].map((row, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-sm text-slate-600 dark:text-slate-400">{row.label}</span>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 line-through">{row.prev}</span>
                  <span className="text-sm font-bold dark:text-white">{row.current}</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                    row.up ? 'bg-green-100 dark:bg-green-900/30 text-green-600' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'
                  }`}>
                    {row.pct}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StatsScreen;
