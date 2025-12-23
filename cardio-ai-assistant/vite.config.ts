import path from 'path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import reactNativeWeb from 'vite-plugin-react-native-web';


export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
    server: {
      port: parseInt(env.VITE_FRONTEND_PORT) || 3000,
      host: '0.0.0.0',
      strictPort: true,
      proxy: {
        '/api': {
          target: 'http://localhost:5001',
          changeOrigin: true,
          secure: false,
        },
      },
    },
    plugins: [react(), reactNativeWeb()],
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
        '@react-native/assets-registry/registry': path.resolve(__dirname, 'mocks/assets-registry.ts'),
        'invariant': path.resolve(__dirname, 'mocks/invariant.ts'),
        'fontfaceobserver': path.resolve(__dirname, 'mocks/fontfaceobserver.ts'),
        'expo-modules-core': path.resolve(__dirname, 'mocks/expo-modules-core.ts'),
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
        'expo-font',
        'expo-modules-core',
      ],
      exclude: [
        '@react-native/assets-registry',
      ],
    },
  };
});
