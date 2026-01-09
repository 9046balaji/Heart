import { useState, useEffect, useCallback } from 'react';
import { Appointment } from '../types';
import { safeGetItem, safeSetItem, STORAGE_KEYS } from '../services/safeStorage';

export const useAppointments = () => {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAppointments();
  }, []);

  const fetchAppointments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const saved = safeGetItem<Appointment[]>(STORAGE_KEYS.USER_APPOINTMENTS, []);
      setAppointments(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch appointments');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fixed: Use functional update to avoid stale closure
  const addAppointment = useCallback((appointment: Appointment) => {
    setAppointments((prev) => {
      const updated = [appointment, ...prev];
      safeSetItem(STORAGE_KEYS.USER_APPOINTMENTS, updated);
      return updated;
    });
  }, []); // No dependencies needed with functional update

  // Fixed: Use functional update to avoid stale closure
  const cancelAppointment = useCallback((id: string) => {
    setAppointments((prev) => {
      const filtered = prev.filter((app) => app.id !== id);
      safeSetItem(STORAGE_KEYS.USER_APPOINTMENTS, filtered);
      return filtered;
    });
  }, []); // No dependencies needed with functional update

  const updateAppointment = useCallback((id: string, updates: Partial<Appointment>) => {
    setAppointments((prev) => {
      const updated = prev.map((app) =>
        app.id === id ? { ...app, ...updates } : app
      );
      safeSetItem(STORAGE_KEYS.USER_APPOINTMENTS, updated);
      return updated;
    });
  }, []);

  return {
    appointments,
    loading,
    error,
    addAppointment,
    cancelAppointment,
    updateAppointment,
    refetch: fetchAppointments,
  };
};
