
import React, { useState } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { statsData, personalBestsData } from '../data/stats';

const StatsScreen: React.FC = () => {
  const [period, setPeriod] = useState<'Week' | 'Month' | 'Year' | 'All-Time'>('Week');
  const data = statsData[period];

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
              <Tooltip
                contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#fff' }}
                cursor={{ stroke: '#137fec', strokeWidth: 1 }}
              />
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
              <Tooltip
                cursor={{fill: 'transparent'}}
                contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '12px', color: '#fff' }}
              />
              <Bar dataKey="val" radius={[4, 4, 4, 4]}>
                {data.frequencyData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.val > 50 ? '#10b981' : '#cbd5e1'} />
                ))}
              </Bar>
              <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} dy={10} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Personal Bests */}
      <div>
        <h3 className="font-bold text-lg dark:text-white mb-4">Personal Records</h3>
        <div className="space-y-3">
          {personalBestsData.map((pb, i) => (
            <div key={i} className="flex items-center gap-4 bg-white dark:bg-card-dark p-4 rounded-xl border border-slate-100 dark:border-slate-800 shadow-sm">
              <div className={`w-12 h-12 rounded-full flex items-center justify-center ${pb.color}`}>
                <span className="material-symbols-outlined">{pb.icon}</span>
              </div>
              <div className="flex-1">
                <p className="text-xs text-slate-500 uppercase font-bold tracking-wider">{pb.title}</p>
                <p className="text-lg font-bold dark:text-white">{pb.value}</p>
              </div>
              <span className="text-xs text-slate-400">{pb.date}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default StatsScreen;
