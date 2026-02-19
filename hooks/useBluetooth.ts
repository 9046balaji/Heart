import { useEffect, useState, useCallback, useRef } from 'react';
import { BleClient, numberToUUID } from '@capacitor-community/bluetooth-le';

// ============================================================================
// Standard BLE Service & Characteristic UUIDs for Health Devices
// ============================================================================

export const BLE_SERVICES = {
  HEART_RATE: numberToUUID(0x180d),
  BATTERY: numberToUUID(0x180f),
  DEVICE_INFO: numberToUUID(0x180a),
  BLOOD_PRESSURE: numberToUUID(0x1810),
  HEALTH_THERMOMETER: numberToUUID(0x1809),
  BODY_COMPOSITION: numberToUUID(0x181b),
  WEIGHT_SCALE: numberToUUID(0x181d),
  RUNNING_SPEED: numberToUUID(0x1814),
  CYCLING_SPEED: numberToUUID(0x1816),
};

export const BLE_CHARACTERISTICS = {
  HEART_RATE_MEASUREMENT: numberToUUID(0x2a37),
  BODY_SENSOR_LOCATION: numberToUUID(0x2a38),
  BATTERY_LEVEL: numberToUUID(0x2a19),
  MANUFACTURER_NAME: numberToUUID(0x2a29),
  MODEL_NUMBER: numberToUUID(0x2a24),
  FIRMWARE_REVISION: numberToUUID(0x2a26),
  BLOOD_PRESSURE_MEASUREMENT: numberToUUID(0x2a35),
  TEMPERATURE_MEASUREMENT: numberToUUID(0x2a1c),
};

// ============================================================================
// Types
// ============================================================================

export interface BluetoothDevice {
  deviceId: string;
  name: string;
  rssi: number;
  services?: string[];
}

export interface SmartwatchData {
  heartRate: number | null;
  heartRateTimestamp: string | null;
  batteryLevel: number | null;
  sensorLocation: string | null;
  manufacturerName: string | null;
  modelNumber: string | null;
}

export interface UseBluetoothReturn {
  isInitialized: boolean;
  isScanning: boolean;
  isConnected: boolean;
  connectedDeviceId: string | null;
  devices: BluetoothDevice[];
  smartwatchData: SmartwatchData;
  error: string | null;
  startScan: () => Promise<void>;
  stopScan: () => Promise<void>;
  connectToDevice: (deviceId: string) => Promise<void>;
  disconnectDevice: (deviceId: string) => Promise<void>;
  readBatteryLevel: (deviceId: string) => Promise<number | null>;
  startHeartRateNotifications: (deviceId: string) => Promise<void>;
  stopHeartRateNotifications: (deviceId: string) => Promise<void>;
}

// ============================================================================
// Helper: Parse Heart Rate Measurement characteristic value
// ============================================================================

function parseHeartRate(value: DataView): number {
  const flags = value.getUint8(0);
  const is16bit = (flags & 0x01) !== 0;

  if (is16bit) {
    return value.getUint16(1, true);
  }
  return value.getUint8(1);
}

function parseSensorLocation(value: number): string {
  const locations: Record<number, string> = {
    0: 'Other',
    1: 'Chest',
    2: 'Wrist',
    3: 'Finger',
    4: 'Hand',
    5: 'Ear Lobe',
    6: 'Foot',
  };
  return locations[value] || 'Unknown';
}

// ============================================================================
// Hook
// ============================================================================

export const useBluetooth = (): UseBluetoothReturn => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectedDeviceId, setConnectedDeviceId] = useState<string | null>(null);
  const [devices, setDevices] = useState<BluetoothDevice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [smartwatchData, setSmartwatchData] = useState<SmartwatchData>({
    heartRate: null,
    heartRateTimestamp: null,
    batteryLevel: null,
    sensorLocation: null,
    manufacturerName: null,
    modelNumber: null,
  });

  const isScanningRef = useRef(false);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Initialize Bluetooth on mount
  useEffect(() => {
    const initBluetooth = async () => {
      try {
        await BleClient.initialize({ androidNeverForLocation: true });
        setIsInitialized(true);
        console.log('✓ Bluetooth initialized');
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        console.error('✗ Bluetooth initialization failed:', errorMsg);
        setError(errorMsg);
      }
    };

    initBluetooth();

    return () => {
      if (isScanningRef.current) {
        BleClient.stopLEScan().catch(() => {});
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  const startScan = useCallback(async () => {
    if (!isInitialized) {
      setError('Bluetooth not initialized. Please enable Bluetooth.');
      return;
    }

    try {
      setIsScanning(true);
      isScanningRef.current = true;
      setDevices([]);
      setError(null);

      await BleClient.requestLEScan(
        {
          services: [], // Empty scans all services; health devices will be found
          allowDuplicates: false,
        },
        (result) => {
          console.log('Device found:', result.device.deviceId, result.device.name);
          setDevices((prev) => {
            const existing = prev.find((d) => d.deviceId === result.device.deviceId);
            if (existing) {
              return prev.map((d) =>
                d.deviceId === result.device.deviceId
                  ? { ...d, rssi: result.rssi ?? d.rssi }
                  : d
              );
            }
            return [
              ...prev,
              {
                deviceId: result.device.deviceId,
                name: result.device.name || 'Unknown Device',
                rssi: result.rssi ?? -100,
                services: result.uuids,
              },
            ];
          });
        }
      );

      console.log('✓ Bluetooth scan started');

      // Auto-stop scan after 15 seconds
      setTimeout(async () => {
        if (isScanningRef.current) {
          await stopScan();
        }
      }, 15000);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Bluetooth scan failed:', errorMsg);

      if (errorMsg.toLowerCase().includes('bluetooth')) {
        setError('Bluetooth is not enabled. Please turn on Bluetooth in your device settings.');
      } else if (errorMsg.toLowerCase().includes('permission')) {
        setError('Bluetooth permission denied. Please allow Bluetooth access in settings.');
      } else {
        setError(errorMsg);
      }
      setIsScanning(false);
      isScanningRef.current = false;
    }
  }, [isInitialized]);

  const stopScan = useCallback(async () => {
    try {
      await BleClient.stopLEScan();
      setIsScanning(false);
      isScanningRef.current = false;
      console.log('✓ Bluetooth scan stopped');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Stop scan failed:', errorMsg);
      setError(errorMsg);
    }
  }, []);

  const connectToDevice = useCallback(async (deviceId: string) => {
    try {
      setError(null);

      await BleClient.connect(deviceId, (disconnectedDeviceId) => {
        console.log(`⚡ Device disconnected: ${disconnectedDeviceId}`);
        setIsConnected(false);
        setConnectedDeviceId(null);

        // Auto-reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(async () => {
          console.log(`🔄 Attempting reconnect to ${disconnectedDeviceId}...`);
          try {
            await BleClient.connect(disconnectedDeviceId);
            setIsConnected(true);
            setConnectedDeviceId(disconnectedDeviceId);
            console.log(`✓ Reconnected to ${disconnectedDeviceId}`);
          } catch {
            console.log('✗ Reconnection failed');
          }
        }, 3000);
      });

      setIsConnected(true);
      setConnectedDeviceId(deviceId);
      console.log(`✓ Connected to device: ${deviceId}`);

      // Try to read device info after connecting
      try {
        await readDeviceInfo(deviceId);
      } catch {
        // Non-critical
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Connection failed:', errorMsg);
      setError(`Connection failed: ${errorMsg}`);
      throw err;
    }
  }, []);

  const disconnectDevice = useCallback(async (deviceId: string) => {
    try {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      try {
        await BleClient.stopNotifications(
          deviceId,
          BLE_SERVICES.HEART_RATE,
          BLE_CHARACTERISTICS.HEART_RATE_MEASUREMENT
        );
      } catch {
        // May not have been started
      }

      await BleClient.disconnect(deviceId);
      setIsConnected(false);
      setConnectedDeviceId(null);
      setSmartwatchData({
        heartRate: null,
        heartRateTimestamp: null,
        batteryLevel: null,
        sensorLocation: null,
        manufacturerName: null,
        modelNumber: null,
      });
      console.log(`✓ Disconnected from device: ${deviceId}`);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Disconnect failed:', errorMsg);
      setError(errorMsg);
    }
  }, []);

  const readBatteryLevel = useCallback(async (deviceId: string): Promise<number | null> => {
    try {
      const result = await BleClient.read(
        deviceId,
        BLE_SERVICES.BATTERY,
        BLE_CHARACTERISTICS.BATTERY_LEVEL
      );
      const level = new DataView(result.buffer).getUint8(0);
      setSmartwatchData(prev => ({ ...prev, batteryLevel: level }));
      console.log(`🔋 Battery level: ${level}%`);
      return level;
    } catch (err) {
      console.warn('Could not read battery level:', err);
      return null;
    }
  }, []);

  const readDeviceInfo = useCallback(async (deviceId: string) => {
    try {
      const mfgResult = await BleClient.read(
        deviceId,
        BLE_SERVICES.DEVICE_INFO,
        BLE_CHARACTERISTICS.MANUFACTURER_NAME
      );
      const manufacturerName = new TextDecoder().decode(mfgResult);

      const modelResult = await BleClient.read(
        deviceId,
        BLE_SERVICES.DEVICE_INFO,
        BLE_CHARACTERISTICS.MODEL_NUMBER
      );
      const modelNumber = new TextDecoder().decode(modelResult);

      setSmartwatchData(prev => ({ ...prev, manufacturerName, modelNumber }));
      console.log(`📱 Device: ${manufacturerName} ${modelNumber}`);
    } catch {
      // Device info service is optional
    }
  }, []);

  const startHeartRateNotifications = useCallback(async (deviceId: string) => {
    try {
      try {
        const locResult = await BleClient.read(
          deviceId,
          BLE_SERVICES.HEART_RATE,
          BLE_CHARACTERISTICS.BODY_SENSOR_LOCATION
        );
        const location = parseSensorLocation(new DataView(locResult.buffer).getUint8(0));
        setSmartwatchData(prev => ({ ...prev, sensorLocation: location }));
      } catch {
        // Sensor location is optional
      }

      await BleClient.startNotifications(
        deviceId,
        BLE_SERVICES.HEART_RATE,
        BLE_CHARACTERISTICS.HEART_RATE_MEASUREMENT,
        (value) => {
          const heartRate = parseHeartRate(value);
          const timestamp = new Date().toISOString();
          setSmartwatchData(prev => ({
            ...prev,
            heartRate,
            heartRateTimestamp: timestamp,
          }));
          console.log(`❤️ Heart Rate: ${heartRate} BPM`);
        }
      );

      console.log('✓ Heart rate notifications started');
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.error('✗ Heart rate notifications failed:', errorMsg);
      setError(`Heart rate monitoring failed: ${errorMsg}`);
    }
  }, []);

  const stopHeartRateNotifications = useCallback(async (deviceId: string) => {
    try {
      await BleClient.stopNotifications(
        deviceId,
        BLE_SERVICES.HEART_RATE,
        BLE_CHARACTERISTICS.HEART_RATE_MEASUREMENT
      );
      console.log('✓ Heart rate notifications stopped');
    } catch (err) {
      console.error('✗ Stop HR notifications failed:', err);
    }
  }, []);

  return {
    isInitialized,
    isScanning,
    isConnected,
    connectedDeviceId,
    devices,
    smartwatchData,
    error,
    startScan,
    stopScan,
    connectToDevice,
    disconnectDevice,
    readBatteryLevel,
    startHeartRateNotifications,
    stopHeartRateNotifications,
  };
};
