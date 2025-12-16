
import React, { useState, useEffect, lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, useLocation, Navigate } from 'react-router-dom';
import './styles/charts.css';

// Eagerly loaded screens (critical path - login/signup)
import LoginScreen from './screens/LoginScreen';
import SignUpScreen from './screens/SignUpScreen';

// Lazily loaded screens for code splitting
const DashboardScreen = lazy(() => import('./screens/DashboardScreen'));
const AssessmentScreen = lazy(() => import('./screens/AssessmentScreen'));
const NutritionScreen = lazy(() => import('./screens/NutritionScreen'));
const ExerciseScreen = lazy(() => import('./screens/ExerciseScreen'));
const AppointmentScreen = lazy(() => import('./screens/AppointmentScreen'));
const ChatScreen = lazy(() => import('./screens/ChatScreen'));
const SettingsScreen = lazy(() => import('./screens/SettingsScreen'));
const ProfileScreen = lazy(() => import('./screens/ProfileScreen'));
const RecipeDetailScreen = lazy(() => import('./screens/RecipeDetailScreen'));
const WorkoutDetailScreen = lazy(() => import('./screens/WorkoutDetailScreen'));
const MedicationScreen = lazy(() => import('./screens/MedicationScreen'));

import BottomNav from './components/BottomNav';
import VoiceControl from './components/VoiceControl';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LanguageProvider } from './contexts/LanguageContext';
import { PageSkeleton, ChatListSkeleton } from './components/Skeleton';

// Loading fallback components for different screen types
const DashboardFallback = () => <PageSkeleton type="dashboard" className="h-screen bg-background-light dark:bg-background-dark" />;
const ChatFallback = () => <PageSkeleton type="chat" className="h-screen bg-background-light dark:bg-background-dark" />;
const ListFallback = () => <PageSkeleton type="list" className="h-screen bg-background-light dark:bg-background-dark" />;
const DetailFallback = () => <PageSkeleton type="detail" className="h-screen bg-background-light dark:bg-background-dark" />;

const AppContent: React.FC = () => {
  const location = useLocation();
  const [isDarkMode, setIsDarkMode] = useState(true);

  // Routes where the bottom navigation should be visible
  const showBottomNav = [
    '/dashboard',
    '/nutrition',
    '/exercise',
    '/profile',
    '/settings',
    '/appointment'
  ].includes(location.pathname);

  // Update HTML class for dark mode
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  const toggleTheme = () => setIsDarkMode(!isDarkMode);

  return (
    <div className="flex flex-col min-h-screen max-w-md mx-auto relative bg-background-light dark:bg-background-dark shadow-2xl overflow-hidden">
      <ErrorBoundary>
        <div className="flex-1 overflow-y-auto no-scrollbar pb-20">
          <Routes>
            <Route path="/" element={<Navigate to="/login" replace />} />
            <Route path="/login" element={<LoginScreen />} />
            <Route path="/signup" element={<SignUpScreen />} />
            
            <Route path="/dashboard" element={
              <Suspense fallback={<DashboardFallback />}>
                <DashboardScreen />
              </Suspense>
            } />
            <Route path="/assessment" element={
              <Suspense fallback={<ListFallback />}>
                <AssessmentScreen />
              </Suspense>
            } />
            <Route path="/nutrition" element={
              <Suspense fallback={<ListFallback />}>
                <NutritionScreen />
              </Suspense>
            } />
            <Route path="/recipe/:id" element={
              <Suspense fallback={<DetailFallback />}>
                <RecipeDetailScreen />
              </Suspense>
            } />
            <Route path="/exercise" element={
              <Suspense fallback={<ListFallback />}>
                <ExerciseScreen />
              </Suspense>
            } />
            <Route path="/workout/:id" element={
              <Suspense fallback={<DetailFallback />}>
                <WorkoutDetailScreen />
              </Suspense>
            } />
            <Route path="/appointment" element={
              <Suspense fallback={<ListFallback />}>
                <AppointmentScreen />
              </Suspense>
            } />
            <Route path="/medications" element={
              <Suspense fallback={<ListFallback />}>
                <MedicationScreen />
              </Suspense>
            } />
            <Route path="/chat" element={
              <Suspense fallback={<ChatFallback />}>
                <ChatScreen />
              </Suspense>
            } />
            <Route path="/settings" element={
              <Suspense fallback={<ListFallback />}>
                <SettingsScreen isDark={isDarkMode} toggleTheme={toggleTheme} />
              </Suspense>
            } />
            <Route path="/profile" element={
              <Suspense fallback={<DetailFallback />}>
                <ProfileScreen />
              </Suspense>
            } />
          </Routes>
        </div>
        
        <VoiceControl />
        {showBottomNav && <BottomNav />}
      </ErrorBoundary>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <LanguageProvider>
        <HashRouter>
            <AppContent />
        </HashRouter>
    </LanguageProvider>
  );
};

export default App;
