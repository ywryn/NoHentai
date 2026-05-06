import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
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
  plugins: [
    vue(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'favicon.svg'],
      manifest: {
        name: 'NoHentai | の変態',
        short_name: 'NoHentai',
        description: 'ExHentai 个人收藏夹信息备份站',
        theme_color: '#0f172a',
        background_color: '#0f172a',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        // 只缓存静态资源，数据 JSON 走网络优先
        globPatterns: ['**/*.{js,css,html,ico,svg,png,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /\/data\/.*\.json$/,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'data-cache',
              networkTimeoutSeconds: 10,
              expiration: {
                maxEntries: 20,
                maxAgeSeconds: 60 * 60 * 24, // 1 天
              },
            },
          },
        ],
      },
    }),
  ],
})
