import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../dist-qc',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'qc-react.js',
        chunkFileNames: 'qc-react-[name].js',
        assetFileNames: 'qc-react-[name].[ext]'
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    port: 3003,
    host: '0.0.0.0'
  }
});
