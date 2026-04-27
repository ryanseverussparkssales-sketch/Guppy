import { defineConfig, devices } from '@playwright/test'

// Match the port Vite uses.  Override with VITE_PORT when the default is busy,
// e.g.: VITE_PORT=3003 npx playwright test
const DEV_PORT = parseInt(process.env.VITE_PORT ?? '3000', 10)
const BASE_URL = `http://localhost:${DEV_PORT}`

export default defineConfig({
  testDir: './src/__tests__/e2e',
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run dev',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
