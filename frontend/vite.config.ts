import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0', // Listen on all interfaces for Docker browser testing
    open: false,
    allowedHosts: ['localhost', 'host.docker.internal'],
  },
  build: {
    outDir: 'build',
  },
  // Handle environment variables - shim process.env for CRA compatibility
  // In production builds (NODE_ENV=production), default to empty string for same-origin API calls
  // In development, use host.docker.internal for Docker browser testing
  define: {
    'process.env.REACT_APP_BACKEND_URL': JSON.stringify(
      process.env.REACT_APP_BACKEND_URL ?? 
      (process.env.NODE_ENV === 'production' ? '' : 'http://host.docker.internal:8000')
    ),
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'development'),
  },
});
