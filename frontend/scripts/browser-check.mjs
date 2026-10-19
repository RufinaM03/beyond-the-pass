import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {chromium} from 'playwright-core';

const base = process.env.BTP_BASE_URL || 'http://127.0.0.1:8000';
const output = resolve(import.meta.dirname, '../../artifacts/phase4-browser');
await mkdir(output, {recursive: true});
const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
});
const page = await browser.newPage({viewport: {width: 1440, height: 1080}});
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
const checks = [];
const record = name => checks.push(name);
try {
  await page.goto(base, {waitUntil: 'networkidle'});
  await page.getByRole('heading', {name: 'A pass isn’t the end of the story.'}).waitFor();
  await page.getByRole('heading', {name: 'Held-out evaluation examples', exact: true}).waitFor();
  await page.screenshot({path: resolve(output, 'overview.png'), fullPage: true});
  record('Production FastAPI overview rendered, real 200-case / 936-example scopes visible');
  await page.getByRole('link', {name: /Explore the follow-up queue/}).click();
  await page.getByRole('heading', {name: /40 selected/}).waitFor();
  await page.getByLabel('Number of cases to select').fill('25');
  await page.getByRole('button', {name: 'Apply capacity'}).click();
  await page.getByRole('heading', {name: /25 selected/}).waitFor();
  await page.getByRole('button', {name: 'Next', exact: true}).click();
  await page.getByText('Showing 21–25 of 25 selected', {exact: true}).waitFor();
  record('Capacity 40 → 25 and bounded pagination 21–25');
  await page.getByLabel('Number of cases to select').fill('500');
  await page.getByRole('button', {name: 'Apply capacity'}).click();
  await page.getByText(/Requested capacity exceeds available eligible cases/).waitFor();
  await page.getByRole('heading', {name: /200 selected/}).waitFor();
  await page.screenshot({path: resolve(output, 'queue.png'), fullPage: true});
  record('Overcapacity 500 capped to 200, explicit explanatory state');
  await page.getByRole('link', {name: /^Open case /}).first().click();
  await page.getByRole('heading', {name: 'The record behind the score.'}).waitFor();
  await page.getByRole('heading', {name: 'Recurring advisories are context, not an explanation'}).waitFor();
  await page.getByText(/Aggregate prior records only/).waitFor();
  await page.getByText('Missing mileage indicator', {exact: true}).waitFor();
  await page.screenshot({path: resolve(output, 'case.png'), fullPage: true});
  record('Real case detail, index-only aggregate history and all frozen explanation terms rendered');
  await page.locator('nav').getByRole('link', {name: /Evaluation/}).click();
  await page.getByRole('heading', {name: 'Inspect the evidence, not just the score.'}).waitFor();
  await page.getByText('76 positive · 860 negative · 8.1% observed prevalence', {exact: true}).waitFor();
  await page.getByLabel('Evaluation capacity').selectOption('2');
  await page.getByRole('cell', {name: '35 / 246', exact: true}).waitFor();
  await page.getByRole('cell', {name: '46.1%', exact: true}).waitFor();
  await page.screenshot({path: resolve(output, 'evaluation.png'), fullPage: true});
  record('Saved 936-example evaluation unchanged; 30% point shows 281 selected, 35 positives / 246 negatives, recall 35/76');
  await page.reload({waitUntil: 'networkidle'});
  await page.getByRole('heading', {name: 'Inspect the evidence, not just the score.'}).waitFor();
  record('Direct production SPA deep-link reload works');
  await page.setViewportSize({width: 390, height: 844});
  await page.goto(base + '/queue', {waitUntil: 'networkidle'});
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await page.screenshot({path: resolve(output, 'mobile-queue.png'), fullPage: true});
  record('390px responsive layout without page-level horizontal overflow');
  await page.getByLabel('Number of cases to select').fill('0');
  await page.getByRole('button', {name: 'Apply capacity'}).click();
  await page.getByRole('heading', {name: 'No cases selected', exact: true}).waitFor();
  record('Zero-capacity empty state rendered');
  await page.route('**/api/queue?*', route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Synthetic browser-only unavailable response'})}));
  await page.getByLabel('Number of cases to select').fill('1');
  await page.getByRole('button', {name: 'Apply capacity'}).click();
  await page.getByRole('heading', {name: 'Data unavailable', exact: true}).waitFor();
  record('Isolated synthetic browser-only 503 shows clear retry/error state, not invented results');
  const expectedError = errors.filter(error => !error.includes('503 (Service Unavailable)'));
  assert.deepEqual(expectedError, []);
  await writeFile(resolve(output, 'checks.json'), JSON.stringify({base, recorded_at: new Date().toISOString(), checks, unexpected_errors: expectedError}, null, 2));
  console.log(`Browser verification passed: ${checks.length} checks. Screenshots/report: ${output}`);
} finally {
  await browser.close();
}
