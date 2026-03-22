import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'path';
import { defineConfig } from 'vite';

// Removes the broken sourceMappingURL comment from @mediapipe bundles at the
// *load* phase so Vite never attempts to open the non-existent .map file.
// Using `transform` is too late — Vite extracts source maps before running transforms.
const stripMediapipeSourcemap = {
  name: 'strip-mediapipe-sourcemap',
  load(id: string) {
    const cleanId = id.split('?')[0];
    if (!cleanId.includes('@mediapipe')) return null;
    try {
      const code = fs.readFileSync(cleanId, 'utf-8');
      return { code: code.replace(/\/\/# sourceMappingURL=\S+\.map/g, ''), map: null };
    } catch {
      return null;
    }
  },
};

export default defineConfig({
  plugins: [react(), stripMediapipeSourcemap],
  optimizeDeps: {
    exclude: ['@mediapipe/tasks-vision'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    sourcemapIgnoreList: (sourcePath) => sourcePath.includes('node_modules/@mediapipe'),
    proxy: {
      '/pubsub': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
