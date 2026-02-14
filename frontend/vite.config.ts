import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }
          if (id.includes('@react-three') || id.includes('three-stdlib') || id.includes('/three/')) {
            return 'vendor-three';
          }
          if (id.includes('react-router')) {
            return 'vendor-router';
          }
          if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('scheduler')) {
            return 'vendor-react';
          }
          if (id.includes('gsap')) {
            return 'vendor-gsap';
          }
          return 'vendor-misc';
        },
      },
    },
  },
  // Enable environment variables
  envPrefix: 'VITE_',
});
