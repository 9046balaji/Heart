import create from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { HealthAssessment, Appointment, Medication, Device, FamilyMember } from '../types';

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  dob?: string;
  bloodType?: string;
  conditions?: string[];
  allergies?: string[];
  emergencyContact?: {
    name: string;
    relation: string;
    phone: string;
  };
}

export interface HealthState {
  // User & Profile
  user: User | null;
  familyMembers: FamilyMember[];

  // Health Data
  appointments: Appointment[];
  vitals: any[];
  medications: Medication[];
  healthAssessment: HealthAssessment | null;

  // Connected Devices
  connectedDevices: Device[];

  // UI State
  loading: boolean;
  error: string | null;

  // Actions
  setUser: (user: User) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;

  // Fetch Actions
  fetchUser: () => Promise<void>;
  fetchAppointments: () => Promise<void>;
  fetchVitals: () => Promise<void>;
  fetchMedications: () => Promise<void>;
  fetchHealthAssessment: () => Promise<void>;

  // Update Actions
  addMedication: (medication: Medication) => Promise<void>;
  removeMedication: (id: string) => void;
  updateVital: (vital: any) => Promise<void>;
  addAppointment: (appointment: Appointment) => Promise<void>;

  // Device Actions
  connectDevice: (device: Device) => void;
  disconnectDevice: (deviceId: string) => void;

  // Reset
  reset: () => void;
}

const initialState = {
  user: null,
  familyMembers: [],
  appointments: [],
  vitals: [],
  medications: [],
  healthAssessment: null,
  connectedDevices: [],
  loading: false,
  error: null,
};

export const useHealthStore = create<HealthState>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        setUser: (user) => set({ user }),
        setLoading: (loading) => set({ loading }),
        setError: (error) => set({ error }),

        fetchUser: async () => {
          set({ loading: true, error: null });
          try {
            // In production, call your backend API
            // const response = await fetch('/api/user');
            // const user = await response.json();
            // set({ user });

            // For now, get from localStorage
            const savedUser = localStorage.getItem('user_profile');
            if (savedUser) {
              set({ user: JSON.parse(savedUser) });
            }
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to fetch user' });
          } finally {
            set({ loading: false });
          }
        },

        fetchAppointments: async () => {
          set({ loading: true, error: null });
          try {
            // In production, call your backend API
            // const response = await fetch('/api/appointments');
            // const appointments = await response.json();
            // set({ appointments });

            const savedAppointments = localStorage.getItem('appointments');
            if (savedAppointments) {
              set({ appointments: JSON.parse(savedAppointments) });
            }
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to fetch appointments' });
          } finally {
            set({ loading: false });
          }
        },

        fetchVitals: async () => {
          set({ loading: true, error: null });
          try {
            const savedVitals = localStorage.getItem('vitals');
            if (savedVitals) {
              set({ vitals: JSON.parse(savedVitals) });
            }
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to fetch vitals' });
          } finally {
            set({ loading: false });
          }
        },

        fetchMedications: async () => {
          set({ loading: true, error: null });
          try {
            const savedMeds = localStorage.getItem('user_medications');
            if (savedMeds) {
              set({ medications: JSON.parse(savedMeds) });
            }
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to fetch medications' });
          } finally {
            set({ loading: false });
          }
        },

        fetchHealthAssessment: async () => {
          set({ loading: true, error: null });
          try {
            const savedAssessment = localStorage.getItem('last_assessment');
            if (savedAssessment) {
              set({ healthAssessment: JSON.parse(savedAssessment) });
            }
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to fetch assessment' });
          } finally {
            set({ loading: false });
          }
        },

        addMedication: async (medication) => {
          try {
            const meds = get().medications;
            const updated = [medication, ...meds];
            set({ medications: updated });
            localStorage.setItem('user_medications', JSON.stringify(updated));
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to add medication' });
          }
        },

        removeMedication: (id) => {
          const meds = get().medications.filter(m => m.id !== id);
          set({ medications: meds });
          localStorage.setItem('user_medications', JSON.stringify(meds));
        },

        updateVital: async (vital) => {
          try {
            const vitals = get().vitals;
            const updated = [vital, ...vitals];
            set({ vitals: updated });
            localStorage.setItem('vitals', JSON.stringify(updated));
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to update vital' });
          }
        },

        addAppointment: async (appointment) => {
          try {
            const appointments = get().appointments;
            const updated = [appointment, ...appointments];
            set({ appointments: updated });
            localStorage.setItem('appointments', JSON.stringify(updated));
          } catch (error) {
            set({ error: error instanceof Error ? error.message : 'Failed to add appointment' });
          }
        },

        connectDevice: (device) => {
          const devices = get().connectedDevices;
          set({ connectedDevices: [device, ...devices] });
        },

        disconnectDevice: (deviceId) => {
          const devices = get().connectedDevices.filter(d => d.id !== deviceId);
          set({ connectedDevices: devices });
        },

        reset: () => set(initialState),
      }),
      {
        name: 'health-store',
        partialize: (state) => ({
          user: state.user,
          medications: state.medications,
          appointments: state.appointments,
          connectedDevices: state.connectedDevices,
        }),
      }
    )
  )
);
