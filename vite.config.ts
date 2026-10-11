import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// GitHub Pages serves the site from /lucca-traffic-twin/; dev and preview use the same base so links match production
export default defineConfig({
  base: '/lucca-traffic-twin/',
  plugins: [react()],
})
