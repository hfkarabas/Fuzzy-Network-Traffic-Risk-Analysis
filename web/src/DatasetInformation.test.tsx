import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import DatasetInformation, { architectureResults, datasetClasses } from './DatasetInformation'
import type { AppData } from './types'
import fixture from './test-fixture.json'
import { setLanguage } from './i18n/store'
import preparation from '../../reports/dataset/preprocessing.json'
import calibration from '../../config/fuzzy/task04/selected_policies.json'

const data = { model: fixture.model, policies: fixture.policies.policies, examples: fixture.examples.examples, evaluation: fixture.evaluation } as unknown as AppData
afterEach(() => { cleanup(); act(() => setLanguage('tr')); localStorage.clear(); vi.unstubAllGlobals() })

it('uses committed class/preparation/architecture facts and the existing policy metadata without inference requests', () => {
  const original = JSON.stringify(data)
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  render(<DatasetInformation data={data} />)
  expect(datasetClasses).toHaveLength(15)
  expect(datasetClasses.reduce((sum, row) => sum + Number(row.count), 0)).toBe(data.model.dataset.records)
  expect(architectureResults.every(row => row.policy === 'Balanced')).toBe(true)
  expect(screen.getByRole('heading', { name: 'Veri Seti Bilgileri' })).toBeVisible()
  expect(screen.getByText('2.827.761')).toBeVisible()
  expect(preparation.source_rows - preparation.excluded_fuzzy_rows).toBe(preparation.fuzzy_rows)
  expect(screen.getByText('Heartbleed')).toBeVisible()
  expect(screen.getByTitle(String(calibration.policies.Balanced.threshold))).toHaveTextContent('51,809237')
  for (const feature of data.model.features) expect(screen.getByText((_text, node) => node?.tagName === 'CODE' && node.textContent === feature.column)).toBeVisible()
  expect(screen.getByRole('link', { name: data.model.dataset.id })).toHaveAttribute('href', `https://huggingface.co/datasets/${data.model.dataset.id}`)
  expect(fetch).not.toHaveBeenCalled()
  expect(JSON.stringify(data)).toBe(original)
})

it('switches the technical page and shared membership plots to English while preserving labels and source identifiers', () => {
  render(<DatasetInformation data={data} />)
  act(() => setLanguage('en'))
  expect(screen.getByRole('heading', { name: 'Dataset Information' })).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Data preparation' })).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Calibration' })).toBeVisible()
  fireEvent.click(screen.getByText('Configured membership curves'))
  expect(screen.getAllByRole('img', { name: /membership functions from the server/ })).toHaveLength(5)
  expect(screen.getByText('Web Attack � XSS')).toBeVisible()
  expect(screen.getByText(/not a conventional machine-learning classifier/)).toBeVisible()
  expect(screen.getByText(/Independent live attack-detection accuracy is not established/)).toBeVisible()
  expect(screen.getByText('reports/fuzzy/task05/comparison.csv')).toBeVisible()
})
