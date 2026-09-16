import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Node's HTTP server aborts slow request bodies after requestTimeout (5 min default),
// which 408s large multipart FASTQ uploads streamed through the dev proxy. Disable it.
const allowLargeUploads = {
  name: 'allow-large-uploads',
  configureServer(server) {
    if (server.httpServer) {
      server.httpServer.requestTimeout = 0
      server.httpServer.headersTimeout = 0
    }
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), allowLargeUploads],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        timeout: 0,
        proxyTimeout: 0,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
