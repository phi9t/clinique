import { expect, test } from '@playwright/test'

const ISSUE_FILTERS = [
  { label: 'Unsafe clearance', marker: 'unsafe clearance' },
  { label: 'Unsupported decision', marker: 'unsupported decision' },
  { label: 'Fabricated quote', marker: 'fabricated quote' },
  { label: 'Incorrect', marker: 'incorrect' },
]

test('PrescreenBench explorer displays case-level workflow and evidence highlights', async ({ page }) => {
  await page.goto('/')

  const prescreenBenchButton = page.getByRole('button', { name: 'PrescreenBench' })
  const familyGroup = page.getByRole('group', { name: 'Dataset family' })

  await expect(familyGroup.getByRole('button', { name: /Regulatory CDISC/i })).toBeVisible()
  await expect(prescreenBenchButton).toBeVisible()
  await prescreenBenchButton.click()

  await expect(page.getByRole('heading', { name: 'PrescreenBench' })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'always_unknown' })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'keyword_rule' })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: 'clinique_rule' })).toBeVisible()
  await expect(page.locator('summary[aria-label^="score:"]').first()).toBeVisible()
  await expect(page.getByText('criterion macro f1').first()).toBeVisible()

  const caseSection = page.locator('section.pb-case-section')
  await expect(caseSection).toBeVisible()

  let activeFilter: (typeof ISSUE_FILTERS)[number]['label'] = ISSUE_FILTERS[0].label
  let activeMarker = ISSUE_FILTERS[0].marker

  // If the deterministic fixture has no unsafe rows, we intentionally fall back to the
  // first metric slice that has at least one visible case.
  for (const [index, issue] of ISSUE_FILTERS.entries()) {
    if (index > 0) {
      const previous = page.getByRole('button', { name: activeFilter })
      await previous.click()
    }

    const filterButton = page.getByRole('button', { name: issue.label })
    await expect(filterButton).toBeVisible()
    await filterButton.click()

    const caseRows = caseSection.locator('tbody tr')
    const hasCaseRows = await caseRows.count()
    if (hasCaseRows > 0) {
      activeFilter = issue.label
      activeMarker = issue.marker
      break
    }
  }

  await expect(page.getByRole('button', { name: activeFilter })).toHaveAttribute('aria-pressed', 'true')
  expect(await caseSection.locator('tbody tr').filter({ hasText: activeMarker }).count()).toBeGreaterThan(
    0,
  )

  const firstCaseRowButton = caseSection.locator('tbody tr').first().locator('button')
  await expect(firstCaseRowButton).toBeVisible()
  await firstCaseRowButton.click()

  await expect(page.getByRole('heading', { name: 'Trial' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Patient' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Criterion comparison by agent' })).toBeVisible()
  const criteriaPanel = page.locator('section.pb-criteria-panel')
  await expect(criteriaPanel.getByRole('columnheader', { name: 'Gold label' }).first()).toBeVisible()
  await expect(criteriaPanel.getByRole('columnheader', { name: 'Prediction' }).first()).toBeVisible()

  const quoteFoundButton = page.getByRole('button', { name: /Quote found/i }).first()
  await expect(quoteFoundButton).toBeVisible()
  await quoteFoundButton.click()
  await expect(page.locator('mark')).toBeVisible()
})
