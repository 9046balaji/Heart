import { useState, useEffect, useCallback } from 'react';

export interface Vital {
  id: string;
  type: string; // 'heart_rate', 'blood_pressure', 'blood_glucose', etc.
  value: number;
  unit: string;
  timestamp: string;
  notes?: string;
}

export const useVitals = () => {
  const [vitals, setVitals] = useState<Vital[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchVitals();
  }, []);

  const fetchVitals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const saved = localStorage.getItem('vitals');
      if (saved) {
        setVitals(JSON.parse(saved));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch vitals');
    } finally {
      setLoading(false);
    }
  }, []);

  const addVital = useCallback((vital: Vital) => {
    const newVitals = [vital, ...vitals];
    setVitals(newVitals);
    localStorage.setItem('vitals', JSON.stringify(newVitals));
  }, [vitals]);

  const getLatestVital = useCallback(
    (type: string): Vital | undefined => {
      return vitals.find((v) => v.type === type);
    },
    [vitals]
  );

  const getVitalTrend = useCallback(
    (type: string, days: number = 7): Vital[] => {
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - days);

      return vitals.filter(
        (v) => v.type === type && new Date(v.timestamp) >= cutoffDate
      );
    },
    [vitals]
  );

  return {
    vitals,
    loading,
    error,
    addVital,
    getLatestVital,
    getVitalTrend,
    refetch: fetchVitals,
  };
};
