import { useEffect, useState, useCallback } from 'react';
import { BleClient } from '@capacitor-community/bluetooth-le';

export interface BluetoothDevice {
  deviceId: string;
  name: string;
  rssi: number;
}

export interface UseBluetoothReturn {
  isInitialized: boolean;
  isScanning: boolean;
  devices: BluetoothDevice[];
  error: string | null;
  startScan: () => Promise<void>;
  stopScan: () => Promise<void>;
  connectToDevice: (deviceId: string) => Promise<void>;
  disconnectDevice: (deviceId: string) => Promise<void>;
}

export const useBluetooth = (): UseBluetoothReturn => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [devices, setDevices] = useState<BluetoothDevice[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Initialize Bluetooth on mount
  useEffect(() => {
    const initBluetooth = async () => {
      try {
        await BleClient.initialize();
        setIsInitialized(true);
        console.log('✓ Bluetooth initialized');
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        console.error('✗ Bluetooth initialization failed:', errorMsg);
        setError(errorMsg);
      }
    };

    initBluetooth();

    // Cleanup on unmount
    return () => {
      if (isScanning) {
        BleClient.stopLEScan().catch(() => {
          // Ignore cleanup errors
        });
      }
    };
  }, [isScanning]);

  const startScan = useCallback(async () => {
    if (!isInitialized) {
      setError('Bluetooth not initialized');
      return;
    }

    try {
      setIsScanning(true);
      setDevices([]);
      setError(null);

      // Start scanning for BLE devices
      await BleClient.requestLEScan(
        {
          services: [], // Empty array scans all services
          allowDuplicates: false,
        },
        (result) => {
          // Process discovered devices
          console.log('Device found:', result.device.deviceId, result.device.name);
          setDevices((prev) => {
            const existing = prev.find((d) => d.deviceId === result.device.deviceId);
            if (existing) {
              return prev.map((d) =>
                d.deviceId === result.device.deviceId ? { ...d, rssi: result.rssi } : d
              );
            }
            return [
              ...prev,
              {
                deviceId: result.device.deviceId,
                name: result.device.name || 'Unknown Device',
                rssi: result.rssi,
              },
            ];
          });
        }
      );

      console.log('✓ Bluetooth scan started');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Bluetooth scan failed:', errorMsg);
      setError(errorMsg);
      setIsScanning(false);
    }
  }, [isInitialized]);

  const stopScan = useCallback(async () => {
    try {
      await BleClient.stopLEScan();
      setIsScanning(false);
      console.log('✓ Bluetooth scan stopped');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Stop scan failed:', errorMsg);
      setError(errorMsg);
    }
  }, []);

  const connectToDevice = useCallback(async (deviceId: string) => {
    try {
      await BleClient.connect(deviceId);
      console.log(`✓ Connected to device: ${deviceId}`);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Connection failed:', errorMsg);
      setError(errorMsg);
    }
  }, []);

  const disconnectDevice = useCallback(async (deviceId: string) => {
    try {
      await BleClient.disconnect(deviceId);
      console.log(`✓ Disconnected from device: ${deviceId}`);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Disconnect failed:', errorMsg);
      setError(errorMsg);
    }
  }, []);

  return {
    isInitialized,
    isScanning,
    devices,
    error,
    startScan,
    stopScan,
    connectToDevice,
    disconnectDevice,
  };
};
