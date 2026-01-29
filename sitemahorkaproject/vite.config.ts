import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  base: '/agrosnab-v1.0/',
  plugins: [react()],
  server: {
    port: 7004,
  },
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
});
