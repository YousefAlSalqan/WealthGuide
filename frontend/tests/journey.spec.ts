import { expect, test, type Page, type TestInfo } from '@playwright/test'

async function captureThemes(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready.then(() => undefined))
  for (const theme of ['light', 'dark']) {
    await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption(theme)
    await expect(page.locator('html')).toHaveAttribute('data-appearance', theme)
    await page.evaluate(() => window.scrollTo(0, 0))
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `${name} ${theme} overflow`).toBeLessThanOrEqual(page.viewportSize()!.width)
    await page.screenshot({ path: info.outputPath(`${name}-${theme}.png`), fullPage: true })
  }
  await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption('system')
}

async function navigate(page: Page, label: string) {
  const menu = page.getByRole('button', { name: 'Open menu', exact: true })
  if (await menu.isVisible()) await menu.click()
  await page.getByRole('button', { name: label, exact: true }).click()
}

test('snapshot, plan, scenario, persistent feedback, history and deletion', async ({ page }, info) => {
  const exceptions: string[] = []
  page.on('pageerror', e => exceptions.push(e.message))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Your money. Let’s talk.' })).toBeVisible()
  await navigate(page, 'Financial snapshot')
  await expect(page.getByRole('button', { name: 'Create my plan' })).toBeVisible()
  await expect(page.getByLabel('Monthly take-home income', { exact: true })).toHaveValue('4200')
  await captureThemes(page, info, 'snapshot')
  const response = page.waitForResponse(r => r.url().endsWith('/v1/analyses') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Create my plan' }).click()
  const result = await (await response).json()
  expect(result.metrics.monthly_surplus).toBe('1300.00')
  expect(result.metrics.allocated_monthly).toBe('1300.00')
  expect(result.status).toBe('complete')
  console.log(`Explanation mode: ${result.ai_status}; model: ${result.model_version || 'none'}`)
  await expect(page.getByRole('heading', { name: 'Your next good money moves' })).toBeVisible()
  await captureThemes(page, info, 'plan')
  await page.getByRole('button', { name: 'Plan to do', exact: true }).first().click()
  await expect(page.getByRole('button', { name: 'Plan to do', exact: true }).first()).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Helpful', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Helpful', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByLabel('Scenario flexible spending').fill('400')
  await page.getByRole('button', { name: 'Compare scenario' }).click()
  await expect(page.getByText('$1,500.00 monthly surplus')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Helpful', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByRole('button', { name: 'Plan to do', exact: true }).first()).toHaveAttribute('aria-pressed', 'true')
  await page.getByRole('button', { name: 'Ask about this plan' }).click()
  await expect(page.getByRole('checkbox', { name: 'Include my selected saved plan' })).toBeChecked()
  await navigate(page, 'Plan history')
  await expect(page.locator('tbody tr')).toHaveCount(1)
  await captureThemes(page, info, 'history')
  await navigate(page, 'Learning library')
  await expect(page.locator('.source-card')).toHaveCount(6)
  await captureThemes(page, info, 'library')
  await navigate(page, 'Privacy & data')
  await captureThemes(page, info, 'privacy')
  await page.getByRole('checkbox').click()
  await expect(page.getByRole('checkbox')).toBeChecked()
  await expect(page.getByText('Your preference has been saved.')).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export my data' }).click()
  expect((await download).suggestedFilename()).toBe('wealthguide-export.json')
  page.once('dialog', d => d.accept())
  await page.getByRole('button', { name: 'Delete my data' }).click()
  await expect(page.getByText('Your previous session and all its saved data were deleted.')).toBeVisible()
  await navigate(page, 'Plan history')
  await expect(page.getByRole('heading', { name: 'A fresh start.' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(exceptions).toEqual([])
})

test('chat persistence and reviewed draft handoff', async ({ page }, info) => {
  const exceptions: string[] = []
  page.on('pageerror', e => exceptions.push(e.message))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Build my snapshot', exact: true })).toBeEnabled()
  await captureThemes(page, info, 'chat')
  await expect(page.getByText('0 of 6', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Build my snapshot', exact: true }).click()
  await expect(page.getByLabel('Message your WealthGuide')).toHaveValue('Help me build my financial snapshot. What should I start with?')
  const posted = page.waitForResponse(r => r.url().endsWith('/v1/chat') && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Send message' }).click()
  const turn = await (await posted).json()
  expect(turn.status).toBe('complete')
  await expect(page.locator('.chat-bubble.assistant')).toContainText(turn.answer)
  await expect(page.getByLabel('Message your WealthGuide')).toBeFocused()
  await expect(page.getByRole('button', { name: 'Review financial snapshot' })).toBeDisabled()
  await page.reload()
  await expect(page.locator('.chat-bubble.user')).toHaveCount(1)
  await expect(page.locator('.chat-bubble.assistant')).toContainText(turn.answer)

  // AI output fixture isolates the form-handoff UI; API persistence/access use the real server above.
  await page.route('**/api/v1/chat', async route => {
    if (route.request().method() !== 'POST') return route.continue()
    const body = route.request().postDataJSON()
    const draft = { cash_balance: '7000', monthly_income: '4500', essential_expenses: '2000', discretionary_expenses: '500', emergency_fund: '1000', debts: [] }
    await route.fulfill({ json: { ...turn, id: crypto.randomUUID(), request_id: body.request_id, message: body.message,
      answer: 'Your details are ready. Review the snapshot before creating your plan.', ai_status: 'generated',
      draft, missing_fields: [], review_issues: [], sources: [],
      snapshot: { ...draft, as_of: new Date().toLocaleDateString('en-CA'), currency: 'USD', emergency_months: 3, goal: null, employer_match: null } } })
  })
  await page.getByLabel('Message your WealthGuide').fill('Here are my fictional details.')
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.getByRole('button', { name: 'Review financial snapshot' })).toBeEnabled()
  await captureThemes(page, info, 'chat-ready')
  await expect(page.getByText('6 of 6', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Review financial snapshot' }).click()
  await expect(page.getByLabel('Total cash balance', { exact: true })).toHaveValue('7000')
  await expect(page.getByLabel('Monthly take-home income', { exact: true })).toHaveValue('4500')
  await expect(page.getByRole('button', { name: 'Create my plan' })).toBeVisible()
  await navigate(page, 'Plan history')
  await expect(page.getByRole('heading', { name: 'A fresh start.' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await navigate(page, 'Privacy & data')
  page.once('dialog', d => d.accept())
  await page.getByRole('button', { name: 'Delete my data' }).click()
  await expect(page.getByText('Your previous session and all its saved data were deleted.')).toBeVisible()
  await navigate(page, 'Chat with your guide')
  await expect(page.getByRole('button', { name: 'Build my snapshot', exact: true })).toBeVisible()
  await expect(page.locator('.chat-bubble.user')).toHaveCount(0)
  expect(exceptions).toEqual([])
})

test('system appearance, contrast tokens, keyboard navigation and small widths', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Build my snapshot', exact: true })).toBeEnabled()
  await expect(page.locator('html')).toHaveCSS('color-scheme', 'dark')
  for (const theme of ['light', 'dark']) {
    await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption(theme)
    await expect(page.locator('html')).toHaveCSS('color-scheme', theme)
    const ratios = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement)
      function luminance(token: string) {
        const hex = style.getPropertyValue(token).trim().slice(1)
        const [r, g, b] = [0, 2, 4].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
          .map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
        return .2126 * r + .7152 * g + .0722 * b
      }
      return [['--control-line', '--bg'], ['--control-line', '--surface'], ['--focus', '--bg'], ['--focus', '--surface'],
        ['--text', '--bg'], ['--muted', '--bg'], ['--muted', '--surface'], ['--muted', '--surface-alt'],
        ['--accent', '--accent-soft'], ['--on-accent', '--accent'], ['--danger', '--danger-bg'], ['--warning', '--warning-bg']]
        .map(([a, b]) => { const x = luminance(a), y = luminance(b); return { pair: `${a}/${b}`, ratio: (Math.max(x, y) + .05) / (Math.min(x, y) + .05) } })
    })
    for (const item of ratios) expect(item.ratio, `${theme} ${item.pair}`).toBeGreaterThanOrEqual(
      item.pair.startsWith('--control-line') || item.pair.startsWith('--focus') ? 3 : 4.5)
  }
  await page.getByRole('combobox', { name: 'Appearance', exact: true }).selectOption('system')
  await page.emulateMedia({ colorScheme: 'light' })
  await expect(page.locator('html')).toHaveCSS('color-scheme', 'light')
  for (const width of [1440, 1280, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `Overflow at ${width}`).toBeLessThanOrEqual(width)
    if (width >= 1280) {
      const rail = await page.locator('.app-header').boundingBox()
      const workspace = await page.locator('main').boundingBox()
      expect(rail!.width).toBe(232)
      expect(workspace!.x).toBeGreaterThanOrEqual(rail!.width)
      await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible()
    }
  }
  const menu = page.getByRole('button', { name: 'Open menu', exact: true })
  await menu.click()
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible()
  await page.getByRole('button', { name: 'Financial snapshot', exact: true }).focus()
  await page.keyboard.press('Escape')
  await expect(menu).toBeFocused()
  await expect(menu).toHaveAttribute('aria-expanded', 'false')
  await navigate(page, 'Privacy & data')
  page.once('dialog', d => d.accept())
  await page.getByRole('button', { name: 'Delete my data' }).click()
  await expect(page.getByText('Your previous session and all its saved data were deleted.')).toBeVisible()
})
