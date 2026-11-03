import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
// Only these small, committed public summaries/configurations are imported by
// Dataset Information. Never allow the repository root or dataset/cache folders.
const informationFiles = [
  '../reports/dataset/preprocessing.json', '../reports/dataset/quality.json',
  '../reports/dataset/classes.csv', '../reports/fuzzy/task05/comparison.csv',
  '../config/fuzzy/task04/selected_policies.json', '../config/fuzzy/task04/selected_v4.json',
].map(path => fileURLToPath(new URL(path, import.meta.url)))
// Vite 8 checks both physical and query-bearing IDs for raw imports.
const rawInformationIds = informationFiles.filter(path => path.endsWith('.csv')).map(path => `${path}?raw`)
export default defineConfig({
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), ...informationFiles, ...rawInformationIds] }, proxy: { '/api': 'http://127.0.0.1:8000', '/openapi.json': 'http://127.0.0.1:8000', '/docs': 'http://127.0.0.1:8000' } },
  test: { environment: 'jsdom', globals: true, setupFiles: './src/test-setup.ts', css: true },
})
