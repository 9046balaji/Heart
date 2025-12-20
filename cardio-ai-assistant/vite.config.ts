import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    server: {
      port: 5174,
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: 'http://localhost:5001',
          changeOrigin: true,
          secure: false,
        },
      },
    },
    plugins: [react()],
    define: {
      'process.env.API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
      global: 'globalThis',
      __DEV__: JSON.stringify(mode === 'development'),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
        'react-native': 'react-native-web',
        'react-native-linear-gradient': 'expo-linear-gradient',
        'react-native-safe-area-context': path.resolve(__dirname, 'components/SafeAreaView.tsx'),
        'react-native/Libraries/Utilities/codegenNativeComponent': 'react-native-web/dist/exports/View',
      },
      extensions: ['.web.js', '.web.jsx', '.web.ts', '.web.tsx', '.js', '.jsx', '.ts', '.tsx', '.json'],
    },
    optimizeDeps: {
      esbuildOptions: {
        resolveExtensions: ['.web.js', '.web.jsx', '.web.ts', '.web.tsx', '.js', '.jsx', '.ts', '.tsx', '.json'],
        loader: {
          '.js': 'jsx',
          '.ts': 'tsx',
        },
        define: {
          global: 'globalThis',
        },
      },
      include: [
        'react',
        'react-dom',
        'react-native-web',
        '@expo/vector-icons',
        'expo-linear-gradient',
      ],
      exclude: [
        '@react-native/assets-registry',
        'expo-font',
        'expo-modules-core',
      ],
    },
  };
});
