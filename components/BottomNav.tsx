
import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';

const BottomNav: React.FC = () => {
  const location = useLocation();
  const { t } = useLanguage();

  const navItems = [
    { icon: 'home', label: t('nav.home'), path: '/dashboard' },
    { icon: 'directions_run', label: t('nav.exercise'), path: '/exercise', filled: true },
    { icon: 'restaurant', label: t('nav.diet'), path: '/nutrition' },
    { icon: 'monitor_heart', label: t('nav.monitor'), path: '/assessment' },
    { icon: 'calendar_month', label: t('nav.book'), path: '/appointment' },
  ];

  return (
    <div className="absolute bottom-0 left-0 right-0 h-[65px] bg-white/90 dark:bg-card-dark/95 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 z-50">
      <div className="flex justify-around items-center h-full px-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.label}
              to={item.path}
              data-discover="true"
              className={`flex flex-col items-center gap-0.5 min-w-[50px] p-1 rounded-xl transition-all duration-300 ${isActive
                  ? 'text-primary'
                  : 'text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300'
                }`}
            >
              <span
                className={`material-symbols-outlined text-2xl ${isActive || item.filled ? 'filled' : ''}`}
                style={item.filled && isActive ? { fontVariationSettings: "'FILL' 1" } : {}}
              >
                {item.icon}
              </span>
              <span className={`text-[10px] font-medium ${isActive ? 'font-bold' : ''}`}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
};

export default BottomNav;
