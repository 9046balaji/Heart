import React, { useState, useEffect } from 'react';
import { apiClient, TimelineEvent } from '../services/apiClient';
import ScreenHeader from '../components/ScreenHeader';

export default function TimelineScreen() {
    const [events, setEvents] = useState<TimelineEvent[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [days, setDays] = useState(30);

    useEffect(() => {
        loadTimeline();
    }, [days]);

    const loadTimeline = async () => {
        try {
            setLoading(true);
            const data = await apiClient.getPatientTimeline('current_user', days);
            setEvents(data);
            setError(null);
        } catch (err) {
            console.error('Failed to load timeline:', err);
            setError('Failed to load timeline. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const getEventIcon = (type: string) => {
        switch (type) {
            case 'lab_result': return 'science';
            case 'prescription': return 'medication';
            case 'vital': return 'favorite';
            case 'appointment': return 'calendar_month';
            case 'alert': return 'warning';
            default: return 'circle';
        }
    };

    const getEventColor = (type: string) => {
        switch (type) {
            case 'lab_result': return { dot: 'bg-indigo-500', iconBg: 'bg-indigo-100 dark:bg-indigo-900/30', iconText: 'text-indigo-600 dark:text-indigo-400' };
            case 'prescription': return { dot: 'bg-emerald-500', iconBg: 'bg-emerald-100 dark:bg-emerald-900/30', iconText: 'text-emerald-600 dark:text-emerald-400' };
            case 'vital': return { dot: 'bg-red-500', iconBg: 'bg-red-100 dark:bg-red-900/30', iconText: 'text-red-600 dark:text-red-400' };
            case 'appointment': return { dot: 'bg-amber-500', iconBg: 'bg-amber-100 dark:bg-amber-900/30', iconText: 'text-amber-600 dark:text-amber-400' };
            case 'alert': return { dot: 'bg-orange-500', iconBg: 'bg-orange-100 dark:bg-orange-900/30', iconText: 'text-orange-600 dark:text-orange-400' };
            default: return { dot: 'bg-slate-400', iconBg: 'bg-slate-100 dark:bg-slate-800', iconText: 'text-slate-500' };
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return {
            day: date.getDate(),
            month: date.toLocaleString('default', { month: 'short' }),
            time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
    };

    return (
        <div className="min-h-screen bg-slate-50 dark:bg-background-dark pb-24 font-sans overflow-x-hidden">
            <ScreenHeader title="Patient Timeline" subtitle="Health Events History" />

            {/* Day Filter */}
            <div className="flex justify-center gap-2 py-3 px-4 bg-white dark:bg-card-dark border-b border-slate-100 dark:border-slate-800">
                {[7, 30, 90].map((d) => (
                    <button
                        key={d}
                        onClick={() => setDays(d)}
                        className={`px-5 py-2 rounded-full text-sm font-semibold transition-colors ${
                            days === d
                                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/20'
                                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
                        }`}
                    >
                        {d} Days
                    </button>
                ))}
            </div>

            <div className="p-4">
                {loading ? (
                    <div className="flex flex-col items-center justify-center py-20">
                        <div className="w-8 h-8 border-3 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
                        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Loading timeline...</p>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center py-20">
                        <span className="material-symbols-outlined text-5xl text-red-500 mb-3">error</span>
                        <p className="text-red-500 text-sm mb-4">{error}</p>
                        <button
                            onClick={loadTimeline}
                            className="px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-semibold hover:bg-indigo-700 transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                ) : events.length === 0 ? (
                    <div className="flex flex-col items-center py-20 text-slate-400 dark:text-slate-500">
                        <span className="material-symbols-outlined text-5xl mb-3">timeline</span>
                        <p className="text-base italic">No events found in this period.</p>
                    </div>
                ) : (
                    <div className="space-y-0">
                        {events.map((event, index) => {
                            const { day, month, time } = formatDate(event.timestamp);
                            const isLast = index === events.length - 1;
                            const colors = getEventColor(event.event_type);

                            return (
                                <div key={event.id} className="flex gap-0">
                                    {/* Date Column */}
                                    <div className="w-[50px] shrink-0 flex flex-col items-center pt-1.5">
                                        <span className="text-lg font-bold text-slate-800 dark:text-white">{day}</span>
                                        <span className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-semibold">{month}</span>
                                        <span className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">{time}</span>
                                    </div>

                                    {/* Line Column */}
                                    <div className="w-[30px] shrink-0 flex flex-col items-center">
                                        <div className={`w-3 h-3 rounded-full mt-2 z-10 ${colors.dot}`}></div>
                                        {!isLast && <div className="w-0.5 flex-1 bg-slate-200 dark:bg-slate-700 -mt-0.5"></div>}
                                    </div>

                                    {/* Card Column */}
                                    <div className="flex-1 pb-5 min-w-0">
                                        <div className="bg-white dark:bg-card-dark rounded-xl p-4 shadow-sm border border-slate-100 dark:border-slate-800">
                                            <div className="flex items-center gap-2.5 mb-2">
                                                <div className={`w-7 h-7 rounded-full flex items-center justify-center ${colors.iconBg}`}>
                                                    <span className={`material-symbols-outlined text-base ${colors.iconText}`}>
                                                        {getEventIcon(event.event_type)}
                                                    </span>
                                                </div>
                                                <h4 className="text-sm font-semibold text-slate-800 dark:text-white flex-1 truncate">
                                                    {event.title}
                                                </h4>
                                            </div>
                                            <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-3">
                                                {event.description}
                                            </p>
                                            <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-700">
                                                <span className="text-[11px] text-slate-400 dark:text-slate-500">Source: {event.source}</span>
                                                {event.verified && (
                                                    <div className="flex items-center gap-1">
                                                        <span className="material-symbols-outlined text-xs text-emerald-500 filled">check_circle</span>
                                                        <span className="text-[11px] text-emerald-500 font-medium">Verified</span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
}
