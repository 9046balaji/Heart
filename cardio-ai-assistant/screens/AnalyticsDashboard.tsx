/**
 * Analytics Dashboard Component
 * 
 * Displays health analytics and insights from the NLP service analytics.py
 * Features:
 * - Usage statistics
 * - Conversation metrics
 * - Health trends visualization
 * - Performance metrics
 */

import React, { useState, useEffect } from 'react';
import { 
  LineChart, Line, BarChart, Bar, PieChart, Pie, 
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, 
  ResponsiveContainer, Cell, AreaChart, Area 
} from 'recharts';

// ============================================================================
// Types
// ============================================================================

interface AnalyticsData {
  overview: {
    totalConversations: number;
    totalMessages: number;
    avgMessagesPerSession: number;
    avgResponseTime: number;
    activeUsers: number;
  };
  conversationsByDay: Array<{
    date: string;
    count: number;
  }>;
  topIntents: Array<{
    intent: string;
    count: number;
    percentage: number;
  }>;
  sentimentDistribution: Array<{
    sentiment: string;
    count: number;
    color: string;
  }>;
  responseTimeHistory: Array<{
    time: string;
    avgResponseTime: number;
    p95ResponseTime: number;
  }>;
  healthQueries: Array<{
    category: string;
    count: number;
  }>;
  userEngagement: {
    newUsers: number;
    returningUsers: number;
    avgSessionDuration: number;
    bounceRate: number;
  };
}

interface AnalyticsDashboardProps {
  className?: string;
}

// ============================================================================
// Mock Data (Replace with actual API calls)
// ============================================================================

const generateMockData = (): AnalyticsData => {
  // Generate last 7 days of data
  const conversationsByDay = Array.from({ length: 7 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (6 - i));
    return {
      date: date.toLocaleDateString('en-US', { weekday: 'short' }),
      count: Math.floor(Math.random() * 50) + 20,
    };
  });

  // Response time history (last 24 hours)
  const responseTimeHistory = Array.from({ length: 24 }, (_, i) => {
    return {
      time: `${i}:00`,
      avgResponseTime: Math.random() * 0.5 + 0.3,
      p95ResponseTime: Math.random() * 1 + 0.8,
    };
  });

  return {
    overview: {
      totalConversations: 1247,
      totalMessages: 8934,
      avgMessagesPerSession: 7.2,
      avgResponseTime: 0.45,
      activeUsers: 342,
    },
    conversationsByDay,
    topIntents: [
      { intent: 'blood_pressure_query', count: 234, percentage: 28 },
      { intent: 'medication_info', count: 189, percentage: 23 },
      { intent: 'symptom_check', count: 156, percentage: 19 },
      { intent: 'appointment_schedule', count: 134, percentage: 16 },
      { intent: 'diet_advice', count: 112, percentage: 14 },
    ],
    sentimentDistribution: [
      { sentiment: 'Positive', count: 523, color: '#10B981' },
      { sentiment: 'Neutral', count: 412, color: '#6B7280' },
      { sentiment: 'Mixed', count: 201, color: '#F59E0B' },
      { sentiment: 'Concerned', count: 111, color: '#EF4444' },
    ],
    responseTimeHistory,
    healthQueries: [
      { category: 'Blood Pressure', count: 312 },
      { category: 'Heart Rate', count: 267 },
      { category: 'Medications', count: 234 },
      { category: 'Symptoms', count: 198 },
      { category: 'Diet', count: 156 },
      { category: 'Exercise', count: 143 },
      { category: 'Appointments', count: 134 },
      { category: 'Sleep', count: 89 },
    ],
    userEngagement: {
      newUsers: 78,
      returningUsers: 264,
      avgSessionDuration: 4.5,
      bounceRate: 23.4,
    },
  };
};

// ============================================================================
// Sub-Components
// ============================================================================

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  color?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, change, icon, color = 'blue' }) => {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400',
    green: 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400',
    purple: 'bg-purple-100 text-purple-600 dark:bg-purple-900/30 dark:text-purple-400',
    orange: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400',
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500 dark:text-slate-400">{title}</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {change >= 0 ? '↑' : '↓'} {Math.abs(change)}% from last week
            </p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color as keyof typeof colorClasses] || colorClasses.blue}`}>
          {icon}
        </div>
      </div>
    </div>
  );
};

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}

const ChartCard: React.FC<ChartCardProps> = ({ title, subtitle, children, className = '' }) => {
  return (
    <div className={`bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm ${className}`}>
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h3>
        {subtitle && (
          <p className="text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  );
};

// ============================================================================
// Main Dashboard Component
// ============================================================================

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({ className = '' }) => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('7d');

  useEffect(() => {
    // Simulate API call
    setLoading(true);
    setTimeout(() => {
      setData(generateMockData());
      setLoading(false);
    }, 1000);
  }, [timeRange]);

  if (loading) {
    return (
      <div className={`p-4 space-y-6 ${className}`}>
        <div className="animate-pulse space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-slate-200 dark:bg-slate-700 h-24 rounded-xl" />
            ))}
          </div>
          <div className="bg-slate-200 dark:bg-slate-700 h-64 rounded-xl" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-slate-200 dark:bg-slate-700 h-64 rounded-xl" />
            <div className="bg-slate-200 dark:bg-slate-700 h-64 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className={`p-4 space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Analytics Dashboard</h1>
          <p className="text-slate-500 dark:text-slate-400">Monitor your health assistant performance</p>
        </div>
        <div className="flex gap-2">
          {(['7d', '30d', '90d'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                timeRange === range
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              {range === '7d' ? 'Week' : range === '30d' ? 'Month' : 'Quarter'}
            </button>
          ))}
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Conversations"
          value={data.overview.totalConversations}
          change={12}
          color="blue"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          }
        />
        <StatCard
          title="Total Messages"
          value={data.overview.totalMessages}
          change={8}
          color="green"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
            </svg>
          }
        />
        <StatCard
          title="Avg Response Time"
          value={`${data.overview.avgResponseTime.toFixed(2)}s`}
          change={-5}
          color="purple"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <StatCard
          title="Active Users"
          value={data.overview.activeUsers}
          change={15}
          color="orange"
          icon={
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
            </svg>
          }
        />
      </div>

      {/* Conversations Chart */}
      <ChartCard title="Conversations Over Time" subtitle="Daily conversation volume">
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={data.conversationsByDay}>
            <defs>
              <linearGradient id="colorConv" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis dataKey="date" stroke="#94A3B8" />
            <YAxis stroke="#94A3B8" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1E293B', 
                border: 'none', 
                borderRadius: '8px',
                color: '#fff'
              }} 
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#3B82F6"
              fillOpacity={1}
              fill="url(#colorConv)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Two Column Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top Intents */}
        <ChartCard title="Top User Intents" subtitle="Most common query types">
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={data.topIntents} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
              <XAxis type="number" stroke="#94A3B8" />
              <YAxis 
                dataKey="intent" 
                type="category" 
                stroke="#94A3B8" 
                width={120}
                tick={{ fontSize: 12 }}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1E293B', 
                  border: 'none', 
                  borderRadius: '8px',
                  color: '#fff'
                }} 
              />
              <Bar dataKey="count" fill="#3B82F6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Sentiment Distribution */}
        <ChartCard title="Sentiment Distribution" subtitle="User sentiment analysis">
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={data.sentimentDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={4}
                  dataKey="count"
                  nameKey="sentiment"
                  label={({ name }) => `${name}`}
                >
                  {data.sentimentDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1E293B', 
                    border: 'none', 
                    borderRadius: '8px',
                    color: '#fff'
                  }} 
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>

      {/* Response Time Chart */}
      <ChartCard title="Response Time" subtitle="Average and P95 response times (24h)">
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={data.responseTimeHistory}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis dataKey="time" stroke="#94A3B8" />
            <YAxis stroke="#94A3B8" unit="s" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1E293B', 
                border: 'none', 
                borderRadius: '8px',
                color: '#fff'
              }} 
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="avgResponseTime" 
              stroke="#10B981" 
              strokeWidth={2}
              dot={false}
              name="Average"
            />
            <Line 
              type="monotone" 
              dataKey="p95ResponseTime" 
              stroke="#F59E0B" 
              strokeWidth={2}
              dot={false}
              name="P95"
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* Health Query Categories */}
      <ChartCard title="Health Query Categories" subtitle="Distribution of health-related queries">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={data.healthQueries}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
            <XAxis dataKey="category" stroke="#94A3B8" angle={-45} textAnchor="end" height={80} />
            <YAxis stroke="#94A3B8" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: '#1E293B', 
                border: 'none', 
                borderRadius: '8px',
                color: '#fff'
              }} 
            />
            <Bar dataKey="count" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      {/* User Engagement */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500 dark:text-slate-400">New Users</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{data.userEngagement.newUsers}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500 dark:text-slate-400">Returning Users</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{data.userEngagement.returningUsers}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <svg className="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500 dark:text-slate-400">Avg Session</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{data.userEngagement.avgSessionDuration.toFixed(1)} min</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white dark:bg-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <svg className="w-5 h-5 text-orange-600 dark:text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            </div>
            <div>
              <p className="text-sm text-slate-500 dark:text-slate-400">Bounce Rate</p>
              <p className="text-xl font-bold text-slate-900 dark:text-white">{data.userEngagement.bounceRate}%</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
