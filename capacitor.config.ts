import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.cardioai.assistant',
  appName: 'CardioAI',
  webDir: 'dist',
  android: {
    allowMixedContent: true,
    captureInput: true,
    webContentsDebuggingEnabled: false,
  },
  server: {
    androidScheme: 'https',
    // For development, point to local dev server:
    // url: 'http://10.0.2.2:3000',
    // cleartext: true,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: '#111111',
      androidSplashResourceName: 'splash',
      androidScaleType: 'CENTER_CROP',
      showSpinner: false,
    },
    Keyboard: {
      resize: 'body' as any,
      style: 'dark' as any,
      resizeOnFullScreen: true,
    },
    StatusBar: {
      style: 'dark' as any,
      backgroundColor: '#111111',
    },
    Camera: {
      presentationStyle: 'fullscreen' as any,
    },
    Browser: {
      windowName: '_system',
    },
  },
};

export default config;
