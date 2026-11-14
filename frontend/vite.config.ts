import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    // Tone.js alone is ~500 kB minified. This is a single-page app served locally for a demo,
    // so one large chunk costs nothing; code-splitting would add complexity for no gain.
    chunkSizeWarningLimit: 1000,
  },
})
