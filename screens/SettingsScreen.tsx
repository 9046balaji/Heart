
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Device } from '../types';
import { useLanguage } from '../contexts/LanguageContext';
import { pdfExportService } from '../services/pdfExport';
import { calendarService, CalendarServiceError } from '../services/calendarService';
import { notificationService, NotificationServiceError } from '../services/notificationService';
import { useToast } from '../components/Toast';
import type { CalendarProvider, WeeklySummaryPreferences, DeliveryChannel } from '../services/api.types';
import { Modal } from '../components/Modal';

interface SettingsProps {
  isDark: boolean;
  toggleTheme: () => void;
}

interface AppSettings {
  notifications: {
    all: boolean;
    meds: boolean;
    insights: boolean;
  };
  preferences: {
    units: 'Metric' | 'Imperial';
  };
}

interface CalendarConnection {
  provider: CalendarProvider;
  connected: boolean;
  email?: string;
  lastSync?: string;
}

import { useAuth } from '../hooks/useAuth';

// --- Extracted Modal Components ---

const DevicesModal = ({
  onClose,
  devices,
  onDisconnect,
  onConnect
}: {
  onClose: () => void,
  devices: Device[],
  onDisconnect: (id: string) => void,
  onConnect: (device: Device) => void
}) => {
  const { t } = useLanguage();
  const [isScanning, setIsScanning] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const startScan = async () => {
    setIsScanning(true);
    setErrorMsg(null);

    // Try Capacitor BLE plugin first (better Android native experience)
    try {
      const { BleClient } = await import('@capacitor-community/bluetooth-le');
      await BleClient.initialize();

      // Request permissions on Android
      await BleClient.requestDevice({
        services: ['0000180d-0000-1000-8000-00805f9b34fb'], // Heart Rate Service UUID
      }).then((device) => {
        const newDevice: Device = {
          id: device.deviceId,
          name: device.name || 'Heart Rate Monitor',
          type: 'chest-strap',
          lastSync: 'Now',
          status: 'connected',
          battery: 100
        };
        onConnect(newDevice);
      });
      setIsScanning(false);
      return;
    } catch (capError: any) {
      // Capacitor BLE not available or failed, fall through to Web Bluetooth
      console.log("Capacitor BLE unavailable, trying Web Bluetooth:", capError.message);
    }

    // Web Bluetooth API Logic (fallback)
    if ('bluetooth' in navigator) {
      try {
        // Request device with Heart Rate Service
        const device = await (navigator as any).bluetooth.requestDevice({
          filters: [{ services: ['heart_rate'] }],
          optionalServices: ['battery_service']
        });

        if (device) {
          // Connect to GATT Server
          const server = await device.gatt.connect();
          console.log("Connected to GATT Server", server);

          // Construct device object for app state
          const newDevice: Device = {
            id: device.id || `ble_${Date.now()}`,
            name: device.name || 'Unknown Heart Rate Monitor',
            type: 'chest-strap', // Assuming chest strap for generic HR
            lastSync: 'Now',
            status: 'connected',
            battery: 100 // Placeholder, would need to read Battery Service
          };

          onConnect(newDevice);
        }
      } catch (error: any) {
        console.error("Bluetooth Error:", error);
        if (error.name !== 'NotFoundError') { // Ignore user cancelled
          setErrorMsg("Connection failed. Ensure device is in pairing mode.");
        }
      } finally {
        setIsScanning(false);
      }
    } else {
      // Fallback for browsers without Web Bluetooth
      setTimeout(() => {
        setErrorMsg("Web Bluetooth is not supported in this browser. Showing simulated device.");
        // Simulate finding a device for demo purposes
        onConnect({
          id: `d_sim_${Date.now()}`, name: 'Simulated HR Monitor', type: 'watch', lastSync: 'Now', status: 'connected', battery: 88
        });
        setIsScanning(false);
      }, 1500);
    }
  };

  return (
    <Modal isOpen={true} onClose={onClose} title={t('settings.devices')}>
      {/* My Devices List */}
      <div className="space-y-3 mb-6 max-h-[40vh] overflow-y-auto pr-1">
        {devices.length > 0 ? devices.map(device => (
          <div key={device.id} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700 animate-in slide-in-from-right">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400">
                <span className="material-symbols-outlined">
                  {device.type === 'watch' ? 'watch' : device.type === 'chest-strap' ? 'monitor_heart' : 'ring_volume'}
                </span>
              </div>
              <div>
                <p className="text-sm font-bold dark:text-white">{device.name}</p>
                <p className="text-xs text-green-500 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span>
                  {t('settings.connected')} {device.battery && `• ${device.battery}%`}
                </p>
              </div>
            </div>
            <button
              onClick={() => onDisconnect(device.id)}
              className="text-xs text-red-500 font-medium hover:bg-red-50 dark:hover:bg-red-900/20 px-2 py-1 rounded-lg transition-colors"
            >
              {t('settings.disconnect')}
            </button>
          </div>
        )) : (
          <div className="text-center py-6 text-slate-500 text-sm italic">No devices connected.</div>
        )}
      </div>

      <div className="border-t border-slate-200 dark:border-slate-700 pt-4">
        {errorMsg && (
          <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs rounded-lg flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">error</span>
            {errorMsg}
          </div>
        )}

        <button
          onClick={startScan}
          disabled={isScanning}
          className={`w-full py-3 bg-primary text-white font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-primary-dark transition-colors shadow-lg shadow-primary/30 ${isScanning ? 'opacity-70 cursor-wait' : ''}`}
        >
          {isScanning ? (
            <>
              <span className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin"></span>
              Scanning...
            </>
          ) : (
            <>
              <span className="material-symbols-outlined">bluetooth_searching</span>
              {t('settings.pair_device')}
            </>
          )}
        </button>

        <p className="text-[10px] text-slate-400 text-center mt-2">
          Make sure your device is in pairing mode.
        </p>
      </div>
    </Modal>
  );
};

const PasswordModal = ({ onClose }: { onClose: () => void }) => {
  const [step, setStep] = useState('form');

  return (
    <Modal isOpen={true} onClose={onClose} title={step === 'form' ? "Change Password" : "Password Updated"}>
      {step === 'form' ? (
        <>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase">Current Password</label>
              <input type="password" className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary" />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase">New Password</label>
              <input type="password" className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary" />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-500 uppercase">Confirm Password</label>
              <input type="password" className="w-full mt-1 p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white focus:ring-2 focus:ring-primary" />
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={onClose} className="flex-1 py-3 text-slate-500 font-bold hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors">Cancel</button>
              <button onClick={() => setStep('success')} className="flex-1 py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30">Update</button>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center py-6 animate-in zoom-in-95 duration-300">
          <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-4 text-green-600 dark:text-green-400">
            <span className="material-symbols-outlined text-3xl">check</span>
          </div>
          <h3 className="text-xl font-bold dark:text-white mb-2">Password Updated</h3>
          <p className="text-slate-500 text-sm mb-6">Your password has been changed successfully.</p>
          <button onClick={onClose} className="w-full py-3 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-bold rounded-xl">Close</button>
        </div>
      )}
    </Modal>
  );
};

const FeedbackModal = ({ onClose }: { onClose: () => void }) => {
  const [sent, setSent] = useState(false);

  return (
    <Modal isOpen={true} onClose={onClose} title={!sent ? "Send Feedback" : "Feedback Sent!"}>
      {!sent ? (
        <>
          <p className="text-slate-500 text-sm mb-4">Let us know how we can improve your experience.</p>
          <textarea
            className="w-full h-32 p-3 bg-slate-100 dark:bg-slate-800 rounded-xl border-none outline-none dark:text-white resize-none mb-4 placeholder:text-slate-400 focus:ring-2 focus:ring-primary"
            placeholder="Type your message here..."
          ></textarea>
          <div className="flex gap-3">
            <button onClick={onClose} className="flex-1 py-3 text-slate-500 font-bold hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl">Cancel</button>
            <button onClick={() => setSent(true)} className="flex-1 py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30">Send</button>
          </div>
        </>
      ) : (
        <div className="text-center py-6 animate-in zoom-in-95 duration-300">
          <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center mx-auto mb-4 text-blue-600 dark:text-blue-400">
            <span className="material-symbols-outlined text-3xl">send</span>
          </div>
          <h3 className="text-xl font-bold dark:text-white mb-2">Feedback Sent!</h3>
          <p className="text-slate-500 text-sm mb-6">Thank you for helping us improve.</p>
          <button onClick={onClose} className="w-full py-3 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-bold rounded-xl">Close</button>
        </div>
      )}
    </Modal>
  );
};

const HelpModal = ({ onClose }: { onClose: () => void }) => (
  <Modal isOpen={true} onClose={onClose} title="Help Center">
    <div className="overflow-y-auto pr-2 space-y-4">
      {[
        { q: "How is my risk score calculated?", a: "Your score is based on the vitals you enter (BP, Cholesterol) combined with lifestyle factors like smoking and activity level." },
        { q: "Is my data private?", a: "Yes, all data is stored locally on your device. We do not share your personal health info." },
        { q: "Can I connect my Fitbit?", a: "Yes! Use the 'Manage Connected Devices' option to scan and pair your Bluetooth trackers." },
        { q: "How do I book an appointment?", a: "Go to the 'Book' tab, search for a specialist, and select an available time slot." }
      ].map((faq, i) => (
        <details key={i} className="group bg-slate-50 dark:bg-slate-800/50 rounded-xl p-3">
          <summary className="flex justify-between items-center cursor-pointer font-bold text-sm dark:text-white list-none">
            {faq.q}
            <span className="material-symbols-outlined text-slate-400 group-open:rotate-180 transition-transform">expand_more</span>
          </summary>
          <p className="text-slate-500 dark:text-slate-400 text-xs mt-2 leading-relaxed">
            {faq.a}
          </p>
        </details>
      ))}
    </div>
    <button className="w-full mt-4 py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30 shrink-0 hover:bg-primary-dark transition-colors">
      Contact Support
    </button>
  </Modal>
);

const TermsModal = ({ onClose }: { onClose: () => void }) => (
  <Modal isOpen={true} onClose={onClose} title="Terms of Service">
    <div className="overflow-y-auto pr-2 text-sm text-slate-600 dark:text-slate-300 leading-relaxed space-y-3">
      <p><strong>1. Acceptance of Terms</strong><br />By accessing and using this application, you accept and agree to be bound by the terms and provision of this agreement.</p>
      <p><strong>2. Medical Disclaimer</strong><br />This app provides information for educational purposes only. It is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician.</p>
      <p><strong>3. User Data</strong><br />We are committed to protecting your privacy. Your personal health data is processed in accordance with our Privacy Policy.</p>
      <p><strong>4. Modifications</strong><br />We reserve the right to modify these terms at any time.</p>
    </div>
    <button onClick={onClose} className="w-full mt-4 py-3 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white font-bold rounded-xl shrink-0 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
      I Agree
    </button>
  </Modal>
);

// --- Calendar Connections Modal ---
const CalendarModal = ({ onClose }: { onClose: () => void }) => {
  const { user } = useAuth();
  const [connections, setConnections] = useState<CalendarConnection[]>(() => {
    const saved = localStorage.getItem('calendar_connections');
    return saved ? JSON.parse(saved) : [
      { provider: 'google' as CalendarProvider, connected: false },
      { provider: 'outlook' as CalendarProvider, connected: false },
    ];
  });
  const [isConnecting, setIsConnecting] = useState<CalendarProvider | null>(null);
  const [isSyncing, setIsSyncing] = useState<CalendarProvider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleConnect = async (provider: CalendarProvider) => {
    if (!user) return;
    setIsConnecting(provider);
    setError(null);

    try {
      // In production, this would trigger OAuth flow
      await new Promise(resolve => setTimeout(resolve, 1500));

      await calendarService.storeCalendarCredentials(user.id, {
        provider,
        access_token: 'demo_token_' + Date.now(),
      });

      const updated = connections.map(c =>
        c.provider === provider
          ? { ...c, connected: true, email: `user@${provider}.com`, lastSync: 'Never' }
          : c
      );
      setConnections(updated);
      localStorage.setItem('calendar_connections', JSON.stringify(updated));

    } catch (err) {
      if (err instanceof CalendarServiceError) {
        setError(err.userMessage);
      } else {
        setError('Failed to connect. Please try again.');
      }
    } finally {
      setIsConnecting(null);
    }
  };

  const handleDisconnect = async (provider: CalendarProvider) => {
    if (!user) return;
    try {
      await calendarService.revokeCalendarCredentials(user.id, provider);

      const updated = connections.map(c =>
        c.provider === provider
          ? { ...c, connected: false, email: undefined, lastSync: undefined }
          : c
      );
      setConnections(updated);
      localStorage.setItem('calendar_connections', JSON.stringify(updated));
    } catch (err) {
      console.error('Disconnect error:', err);
    }
  };

  const handleSync = async (provider: CalendarProvider) => {
    if (!user) return;
    setIsSyncing(provider);
    setError(null);

    try {
      await calendarService.syncCalendar(user.id, {
        provider,
        days_ahead: 30,
        include_reminders: true,
      });

      const updated = connections.map(c =>
        c.provider === provider
          ? { ...c, lastSync: 'Just now' }
          : c
      );
      setConnections(updated);
      localStorage.setItem('calendar_connections', JSON.stringify(updated));

    } catch (err) {
      if (err instanceof CalendarServiceError) {
        setError(err.userMessage);
      } else {
        setError('Sync failed. Please try again.');
      }
    } finally {
      setIsSyncing(null);
    }
  };

  const getProviderColor = (provider: CalendarProvider) => {
    return provider === 'google'
      ? 'text-red-500 bg-red-50 dark:bg-red-900/20'
      : 'text-blue-500 bg-blue-50 dark:bg-blue-900/20';
  };

  return (
    <Modal isOpen={true} onClose={onClose} title="Calendar Connections">
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
        Connect your calendars to sync appointments and set reminders.
      </p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
          <p className="text-red-700 dark:text-red-400 text-sm flex items-center gap-2">
            <span className="material-symbols-outlined text-sm">error</span>
            {error}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {connections.map(conn => (
          <div key={conn.provider} className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${getProviderColor(conn.provider)}`}>
                  <span className="material-symbols-outlined">{conn.provider === 'google' ? 'event' : 'calendar_month'}</span>
                </div>
                <div>
                  <p className="font-medium dark:text-white capitalize">{conn.provider}</p>
                  {conn.connected && conn.email && (
                    <p className="text-xs text-slate-500">{conn.email}</p>
                  )}
                </div>
              </div>
              {conn.connected ? (
                <span className="text-xs text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30 px-2 py-1 rounded-full font-medium flex items-center gap-1">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                  Connected
                </span>
              ) : (
                <span className="text-xs text-slate-500 dark:text-slate-400">Not connected</span>
              )}
            </div>

            {conn.connected ? (
              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => handleSync(conn.provider)}
                  disabled={isSyncing === conn.provider}
                  className="flex-1 py-2 bg-primary/10 text-primary rounded-lg text-sm font-medium flex items-center justify-center gap-1 hover:bg-primary/20 transition-colors disabled:opacity-50"
                >
                  {isSyncing === conn.provider ? (
                    <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin"></span>
                  ) : (
                    <span className="material-symbols-outlined text-sm">sync</span>
                  )}
                  {conn.lastSync ? `Last: ${conn.lastSync}` : 'Sync Now'}
                </button>
                <button
                  onClick={() => handleDisconnect(conn.provider)}
                  className="py-2 px-3 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg text-sm font-medium transition-colors"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <button
                onClick={() => handleConnect(conn.provider)}
                disabled={isConnecting === conn.provider}
                className="w-full mt-3 py-2 bg-primary text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 hover:bg-primary-dark transition-colors shadow-lg shadow-primary/20 disabled:opacity-50"
              >
                {isConnecting === conn.provider ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin"></span>
                    Connecting...
                  </>
                ) : (
                  <>
                    <span className="material-symbols-outlined text-sm">link</span>
                    Connect {conn.provider.charAt(0).toUpperCase() + conn.provider.slice(1)}
                  </>
                )}
              </button>
            )}
          </div>
        ))}
      </div>
    </Modal>
  );
};

// --- Weekly Summary Modal ---
const WeeklySummaryModal = ({ onClose }: { onClose: () => void }) => {
  const { user } = useAuth();
  const [preferences, setPreferences] = useState<WeeklySummaryPreferences>({
    enabled: false,
    delivery_channels: [
      { channel: 'email', enabled: true, destination: 'user@example.com' },
      { channel: 'push', enabled: false },
      { channel: 'whatsapp', enabled: false },
    ],
    preferred_day: 0,
    preferred_time: '09:00',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadPrefs = async () => {
      if (!user) return;
      try {
        const prefs = await notificationService.getWeeklySummaryPreferences(user.id);
        setPreferences(prefs);
      } catch (err) {
        console.log('Using default weekly summary preferences');
      }
    };
    loadPrefs();
  }, [user]);

  const handleSave = async () => {
    if (!user) return;
    setIsSaving(true);
    setError(null);

    try {
      await notificationService.updateWeeklySummaryPreferences(user.id, preferences);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err instanceof NotificationServiceError) {
        setError(err.userMessage);
      } else {
        setError('Failed to save. Please try again.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  const toggleChannel = (channel: 'push' | 'email' | 'whatsapp') => {
    setPreferences(prev => ({
      ...prev,
      delivery_channels: prev.delivery_channels.map(c =>
        c.channel === channel ? { ...c, enabled: !c.enabled } : c
      ),
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200" onClick={onClose}>
      <div className="bg-white dark:bg-card-dark rounded-2xl p-6 w-full max-w-sm shadow-2xl max-h-[80vh] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4 shrink-0">
          <h3 className="text-xl font-bold dark:text-white">Weekly Summary</h3>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors text-slate-500">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="overflow-y-auto flex-1 space-y-4">
          {/* Enable Toggle */}
          <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center text-purple-600">
                <span className="material-symbols-outlined">summarize</span>
              </div>
              <div>
                <p className="font-medium dark:text-white">Enable Weekly Summary</p>
                <p className="text-xs text-slate-500">Get a personalized health recap</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                className="sr-only peer"
                checked={preferences.enabled}
                onChange={() => setPreferences(prev => ({ ...prev, enabled: !prev.enabled }))}
              />
              <div className="w-11 h-6 bg-slate-200 dark:bg-slate-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
            </label>
          </div>

          {preferences.enabled && (
            <>
              {/* Delivery Channels */}
              <div>
                <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">Delivery Channels</label>
                <div className="space-y-2">
                  {preferences.delivery_channels.map(dc => (
                    <div key={dc.channel} className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-slate-400">
                          {dc.channel === 'email' ? 'mail' : dc.channel === 'push' ? 'notifications' : 'chat'}
                        </span>
                        <span className="text-sm font-medium dark:text-white capitalize">{dc.channel}</span>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          className="sr-only peer"
                          checked={dc.enabled}
                          onChange={() => toggleChannel(dc.channel as 'push' | 'email' | 'whatsapp')}
                        />
                        <div className="w-9 h-5 bg-slate-200 dark:bg-slate-700 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Day Selector */}
              <div>
                <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">Delivery Day</label>
                <select
                  value={preferences.preferred_day}
                  onChange={e => setPreferences(prev => ({ ...prev, preferred_day: parseInt(e.target.value) }))}
                  className="w-full p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white appearance-none cursor-pointer"
                >
                  {notificationService.DAYS_OF_WEEK.map(day => (
                    <option key={day.value} value={day.value}>{day.label}</option>
                  ))}
                </select>
              </div>

              {/* Time Selector */}
              <div>
                <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">Delivery Time</label>
                <input
                  type="time"
                  value={preferences.preferred_time}
                  onChange={e => setPreferences(prev => ({ ...prev, preferred_time: e.target.value }))}
                  className="w-full p-3 rounded-xl bg-slate-100 dark:bg-slate-800 border-none outline-none dark:text-white"
                />
              </div>
            </>
          )}

          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
              <p className="text-red-700 dark:text-red-400 text-sm">{error}</p>
            </div>
          )}
        </div>

        <button
          onClick={handleSave}
          disabled={isSaving}
          className="w-full mt-4 py-3 bg-primary text-white font-bold rounded-xl shadow-lg shadow-primary/30 shrink-0 hover:bg-primary-dark transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {isSaving ? (
            <>
              <span className="w-4 h-4 border-2 border-white/50 border-t-white rounded-full animate-spin"></span>
              Saving...
            </>
          ) : saved ? (
            <>
              <span className="material-symbols-outlined">check</span>
              Saved!
            </>
          ) : (
            'Save Preferences'
          )}
        </button>
      </div>
    </div>
  );
};

// --- Main Screen Component ---

const SettingsScreen: React.FC<SettingsProps> = ({ isDark, toggleTheme }) => {
  const navigate = useNavigate();
  const { t, language, setLanguage } = useLanguage();
  const { showToast } = useToast();
  const [activeModal, setActiveModal] = useState<string | null>(null);

  // Initialize state from localStorage or defaults
  const [settings, setSettings] = useState<AppSettings>(() => {
    const saved = localStorage.getItem('app_settings');
    return saved ? JSON.parse(saved) : {
      notifications: {
        all: true,
        meds: true,
        insights: false,
      },
      preferences: {
        units: 'Metric',
      }
    };
  });

  // Connected Devices State
  const [devices, setDevices] = useState<Device[]>(() => {
    const saved = localStorage.getItem('connected_devices');
    return saved ? JSON.parse(saved) : [
      { id: 'd1', name: 'Apple Watch Series 8', type: 'watch', lastSync: 'Today, 10:30 AM', status: 'connected', battery: 82 },
      { id: 'd2', name: 'Oura Ring', type: 'ring', lastSync: 'Yesterday', status: 'connected', battery: 45 }
    ];
  });

  // Save settings
  useEffect(() => {
    localStorage.setItem('app_settings', JSON.stringify(settings));
  }, [settings]);

  // Save devices
  useEffect(() => {
    localStorage.setItem('connected_devices', JSON.stringify(devices));
  }, [devices]);

  const toggleNotification = (key: keyof AppSettings['notifications']) => {
    // Request Permission for All Notifications
    if (key === 'all' && !settings.notifications.all) {
      if ('Notification' in window) {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') {
            console.log('Notification permission granted.');
          }
        });
      }
    }

    setSettings(prev => ({
      ...prev,
      notifications: {
        ...prev.notifications,
        [key]: !prev.notifications[key]
      }
    }));
  };

  const toggleUnits = () => {
    setSettings(prev => ({
      ...prev,
      preferences: {
        ...prev.preferences,
        units: prev.preferences.units === 'Metric' ? 'Imperial' : 'Metric'
      }
    }));
  };

  const cycleLanguage = () => {
    const languages: ('en' | 'es' | 'fr' | 'te')[] = ['en', 'es', 'fr', 'te'];
    const currentIndex = languages.indexOf(language);
    const nextIndex = (currentIndex + 1) % languages.length;
    setLanguage(languages[nextIndex]);
  };

  const closeModal = () => setActiveModal(null);

  const handleConnectDevice = (newDevice: Device) => {
    setDevices(prev => [...prev, newDevice]);
  };

  const handleDisconnectDevice = (id: string) => {
    setDevices(prev => prev.filter(d => d.id !== id));
  };

  const ToggleSwitch = ({ checked, onChange }: { checked: boolean; onChange?: () => void }) => (
    <label className="relative inline-flex items-center cursor-pointer" onClick={(e) => e.stopPropagation()}>
      <input
        type="checkbox"
        className="sr-only peer"
        checked={checked}
        onChange={onChange || (() => { })}
      />
      <div className="w-11 h-6 bg-slate-200 dark:bg-slate-700 rounded-full peer peer-focus:ring-2 peer-focus:ring-primary/50 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary"></div>
    </label>
  );

  return (
    <div className="relative flex h-auto min-h-screen w-full flex-col bg-background-light dark:bg-background-dark font-sans pb-24 overflow-x-hidden">
      {/* Top App Bar */}
      <div className="flex items-center p-4 pb-2 justify-between bg-background-light dark:bg-background-dark sticky top-0 z-10">
        <button
          onClick={() => navigate('/profile')}
          className="flex w-10 h-10 items-center justify-center text-slate-700 dark:text-slate-200 rounded-full hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <span className="material-symbols-outlined">arrow_back_ios_new</span>
        </button>
        <h2 className="text-slate-900 dark:text-white text-lg font-bold leading-tight flex-1 text-center pr-10">
          {t('settings.title')}
        </h2>
      </div>

      {/* Search Bar */}
      <div className="px-4 py-3">
        <label className="flex flex-col min-w-40 h-12 w-full">
          <div className="flex w-full flex-1 items-stretch rounded-lg h-full">
            <div className="text-slate-400 dark:text-slate-500 flex border-none bg-slate-100 dark:bg-slate-800 items-center justify-center pl-4 rounded-l-lg border-r-0">
              <span className="material-symbols-outlined">search</span>
            </div>
            <input
              className="form-input flex w-full min-w-0 flex-1 resize-none overflow-hidden rounded-lg text-slate-900 dark:text-white focus:outline-0 focus:ring-0 border-none bg-slate-100 dark:bg-slate-800 focus:border-none h-full placeholder:text-slate-400 dark:placeholder:text-slate-500 px-4 rounded-l-none border-l-0 pl-2 text-base font-normal leading-normal"
              placeholder={t('settings.search_placeholder')}
              defaultValue=""
            />
          </div>
        </label>
      </div>

      <div className="px-4">
        <div className="bg-slate-200 dark:bg-slate-800 h-px w-full"></div>
      </div>

      <div className="space-y-6 pb-12">
        {/* Account Management Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-6">
            {t('settings.account')}
          </h3>
          <div
            onClick={() => navigate('/profile')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">person</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.profile')}</p>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
          <div
            onClick={() => setActiveModal('password')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">lock</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.password')}</p>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
          <div
            onClick={() => setActiveModal('devices')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">watch</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.devices')}</p>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <span className="bg-primary text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md">{devices.length}</span>
              <span className="material-symbols-outlined text-slate-400 dark:text-slate-500">chevron_right</span>
            </div>
          </div>
        </div>

        {/* App Preferences Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-4">
            {t('settings.preferences')}
          </h3>
          <div
            onClick={cycleLanguage}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">language</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.language')}</p>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <span className="text-sm text-primary font-bold bg-primary/10 px-2 py-1 rounded-md uppercase">{language}</span>
              <span className="material-symbols-outlined text-slate-400 dark:text-slate-500">sync_alt</span>
            </div>
          </div>
          <div
            onClick={toggleUnits}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">straighten</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.units')}</p>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <span className="text-sm text-slate-500 dark:text-slate-400">{settings.preferences.units}</span>
              <span className="material-symbols-outlined text-slate-400 dark:text-slate-500">swap_horiz</span>
            </div>
          </div>
          <div
            onClick={toggleTheme}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">contrast</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.theme')}</p>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <span className="text-sm text-slate-500 dark:text-slate-400">{isDark ? t('settings.dark') : t('settings.light')}</span>
              <span className="material-symbols-outlined text-slate-400 dark:text-slate-500">toggle_on</span>
            </div>
          </div>
        </div>

        {/* Integrations Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-4">
            Integrations
          </h3>
          <div
            onClick={() => setActiveModal('calendar')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">calendar_month</span>
              </div>
              <div>
                <p className="text-slate-900 dark:text-white text-base font-normal leading-normal truncate">Calendar Connections</p>
                <p className="text-slate-500 dark:text-slate-400 text-xs">Connect Google & Outlook</p>
              </div>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
          <div
            onClick={() => setActiveModal('weeklySummary')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">summarize</span>
              </div>
              <div>
                <p className="text-slate-900 dark:text-white text-base font-normal leading-normal truncate">Weekly Summary</p>
                <p className="text-slate-500 dark:text-slate-400 text-xs">Configure your health recap</p>
              </div>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
        </div>

        {/* Notifications Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-4">
            {t('settings.notifications')}
          </h3>
          <div
            onClick={() => toggleNotification('all')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">notifications</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.notif_all')}</p>
            </div>
            <div className="shrink-0">
              <ToggleSwitch checked={settings.notifications.all} onChange={() => toggleNotification('all')} />
            </div>
          </div>
          <div
            onClick={() => toggleNotification('meds')}
            className={`flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${!settings.notifications.all ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">pill</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.notif_meds')}</p>
            </div>
            <div className="shrink-0">
              <ToggleSwitch checked={settings.notifications.meds} onChange={() => toggleNotification('meds')} />
            </div>
          </div>
          <div
            onClick={() => toggleNotification('insights')}
            className={`flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${!settings.notifications.all ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">insights</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.notif_insights')}</p>
            </div>
            <div className="shrink-0">
              <ToggleSwitch checked={settings.notifications.insights} onChange={() => toggleNotification('insights')} />
            </div>
          </div>
        </div>

        {/* Data Management Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-4">
            Data Management
          </h3>
          <div
            onClick={() => {
              pdfExportService.exportQuickSummary();
            }}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">picture_as_pdf</span>
              </div>
              <div>
                <p className="text-slate-900 dark:text-white text-base font-normal leading-normal truncate">Export Health Report</p>
                <p className="text-slate-500 dark:text-slate-400 text-xs">Download your data as PDF</p>
              </div>
            </div>
            <div className="shrink-0 text-primary">
              <span className="material-symbols-outlined">download</span>
            </div>
          </div>
          <div
            onClick={() => {
              // Get chat messages from localStorage
              const messages = JSON.parse(localStorage.getItem('chat_messages') || '[]');
              if (messages.length > 0) {
                pdfExportService.exportChatHistory({
                  messages,
                  exportDate: new Date(),
                });
              } else {
                showToast('No chat history to export.', 'info');
              }
            }}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">chat</span>
              </div>
              <div>
                <p className="text-slate-900 dark:text-white text-base font-normal leading-normal truncate">Export Chat History</p>
                <p className="text-slate-500 dark:text-slate-400 text-xs">Save conversations as PDF</p>
              </div>
            </div>
            <div className="shrink-0 text-primary">
              <span className="material-symbols-outlined">download</span>
            </div>
          </div>
        </div>

        {/* Support & Feedback Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-4">
            {t('settings.support')}
          </h3>
          <div
            onClick={() => setActiveModal('help')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">help_center</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.help')}</p>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
          <div
            onClick={() => setActiveModal('feedback')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">feedback</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.feedback')}</p>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
        </div>

        {/* About Section */}
        <div>
          <h3 className="text-slate-900 dark:text-white text-lg font-bold leading-tight px-4 pb-2 pt-4">
            {t('settings.about')}
          </h3>
          <div className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between">
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">info</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.version')}</p>
            </div>
            <div className="shrink-0">
              <span className="text-sm text-slate-500 dark:text-slate-400">1.0.2</span>
            </div>
          </div>
          <div
            onClick={() => setActiveModal('terms')}
            className="flex items-center gap-4 bg-background-light dark:bg-background-dark px-4 min-h-14 justify-between cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
          >
            <div className="flex items-center gap-4">
              <div className="text-slate-700 dark:text-slate-200 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-slate-800 shrink-0 size-10">
                <span className="material-symbols-outlined">gavel</span>
              </div>
              <p className="text-slate-900 dark:text-white text-base font-normal leading-normal flex-1 truncate">{t('settings.terms')}</p>
            </div>
            <div className="shrink-0 text-slate-400 dark:text-slate-500">
              <span className="material-symbols-outlined">chevron_right</span>
            </div>
          </div>
        </div>
      </div>

      {/* Render Active Modal */}
      {activeModal === 'password' && <PasswordModal onClose={closeModal} />}
      {activeModal === 'devices' && (
        <DevicesModal
          onClose={closeModal}
          devices={devices}
          onDisconnect={handleDisconnectDevice}
          onConnect={handleConnectDevice}
        />
      )}
      {activeModal === 'help' && <HelpModal onClose={closeModal} />}
      {activeModal === 'feedback' && <FeedbackModal onClose={closeModal} />}
      {activeModal === 'terms' && <TermsModal onClose={closeModal} />}
      {activeModal === 'calendar' && <CalendarModal onClose={closeModal} />}
      {activeModal === 'weeklySummary' && <WeeklySummaryModal onClose={closeModal} />}
    </div>
  );
};

export default SettingsScreen;
