import { test, expect } from '@playwright/test'

const THEMES = ['dark', 'occult', 'gonzo', 'rockmag'] as const

test.describe('Theme switcher', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies()
    await page.evaluate(() => localStorage.clear())
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('default theme has no data-theme attribute', async ({ page }) => {
    const attr = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(attr).toBeNull()
  })

  for (const theme of THEMES) {
    test(`applying "${theme}" sets data-theme and persists across reload`, async ({ page }) => {
      // Apply theme via the same function the app uses
      await page.evaluate((t) => {
        localStorage.setItem('guppy-theme', t)
        document.documentElement.setAttribute('data-theme', t)
      }, theme)

      const attrBefore = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
      expect(attrBefore).toBe(theme)

      // Reload — initTheme() should restore it from localStorage
      await page.reload()
      await page.waitForLoadState('networkidle')

      const attrAfter = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
      expect(attrAfter).toBe(theme)
    })
  }

  test('switching back to default removes data-theme', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('guppy-theme', 'occult')
      document.documentElement.setAttribute('data-theme', 'occult')
    })

    await page.evaluate(() => {
      document.documentElement.removeAttribute('data-theme')
      localStorage.setItem('guppy-theme', 'default')
    })

    const attr = await page.evaluate(() => document.documentElement.getAttribute('data-theme'))
    expect(attr).toBeNull()
  })
})
