import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
  base: '/',
  server: {
    host: '0.0.0.0',
    port: 3000,
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      'chartjs-chart-matrix': resolve(__dirname, 'node_modules/chartjs-chart-matrix/dist/chartjs-chart-matrix.esm.js'),
    },
  },
  plugins: [vue()],
})
