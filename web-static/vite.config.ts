import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import { createReadStream, existsSync } from 'fs'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
  base: '/',
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/data': 'http://127.0.0.1:8000',
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
      'chartjs-chart-matrix': resolve(__dirname, 'node_modules/chartjs-chart-matrix/dist/chartjs-chart-matrix.esm.js'),
    },
  },
  plugins: [
    {
      name: 'serve-kuromoji-dict',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (!req.url?.startsWith('/kuromoji-dict/')) return next()
          const file = resolve(__dirname, 'public', req.url.slice(1))
          if (!existsSync(file)) return next()
          res.statusCode = 200
          res.setHeader('Content-Type', 'application/octet-stream')
          res.setHeader('Cache-Control', 'public, max-age=31536000')
          createReadStream(file).pipe(res)
        })
      },
    },
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
        /* 不锁方向：阅读器的双页对开模式必须横屏才有意义 */
        orientation: 'any',
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
        // 只缓存静态资源，数据库内容始终访问后端。
        globPatterns: ['**/*.{js,css,html,ico,svg,png,woff2}'],
        runtimeCaching: [
          {
            // 管理保存后立即生效，避免回退旧快照。
            urlPattern: /\/data\/.*\.(?:json|csv)$/,
            handler: 'NetworkOnly',

          },
        ],
      },
    }),
  ],
  build: {
    rollupOptions: {
      output: {
        // 把体积大且非首屏必需的依赖拆出去，避免拖慢首屏
        manualChunks: {
          vendor: ['vue', 'vue-router'],
          charts: ['chart.js', 'chartjs-chart-matrix'],
          opencc: ['opencc-js'],
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
})
