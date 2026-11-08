import { formatNumber, formatFixed, LOCALE } from './format'
import type { AppData } from './types'
import { Card, MembershipChart } from './components/FuzzyAnalysis'
// Small committed summaries only: no source dataset, capture or inference import.
import preparation from '../../reports/dataset/preprocessing.json'
import quality from '../../reports/dataset/quality.json'
import calibration from '../../config/fuzzy/task04/selected_policies.json'
import production from '../../config/fuzzy/task04/selected_v4.json'
import classCSV from '../../reports/dataset/classes.csv?raw'
import architectureCSV from '../../reports/fuzzy/task05/comparison.csv?raw'

// These two committed CSV summaries contain no quoted/comma-bearing fields.
export function summaryRows(source: string): Record<string, string>[] {
  const [header, ...rows] = source.trim().split(/\r?\n/)
  const columns = header.split(',')
  return rows.map(row => {
    const values = row.split(',')
    if (values.length !== columns.length) throw new Error('Invalid committed summary CSV')
    return Object.fromEntries(columns.map((column, i) => [column, values[i]]))
  })
}
export const datasetClasses = summaryRows(classCSV)
export const architectureResults = summaryRows(architectureCSV).filter(row => row.policy === 'Balanced')
const percent = (value: number) => `${new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 4 }).format(value * 100)}%`
function Source({ paths }: { paths: string[] }) {
  return (<p className="dataset-source">Source artifacts: {paths.map(path => <code key={path}>{path}</code>)}</p>)
}

export default function DatasetInformation({ data }: { data: AppData }) {
  const aligned = calibration.model_id === data.model.model_id
  return (<div className="dataset-information">
    <div className="page-title"><h1>Dataset Information</h1><p>Dataset provenance, model development and recorded evaluation scope</p></div>
    <nav className="dataset-sections" aria-label="Dataset information sections">{['Dataset', 'Data preparation', 'Model architecture', 'Model development', 'Calibration', 'Evaluation', 'Limitations'].map((label, i) => <button key={label} onClick={() => document.getElementById(`dataset-section-${i}`)?.scrollIntoView?.({ block: 'start' })}>{label}</button>)}</nav>

    <Card className="dataset-section"><h2 id="dataset-section-0">Dataset</h2>
      <div className="dataset-facts"><div><small>Source</small><strong>CIC-IDS2017</strong></div><div><small>Record count</small><strong>{formatNumber(data.model.dataset.records)}</strong></div><div><small>Source columns</small><strong>{data.model.dataset.columns}</strong><small>78 numerical fields and the label</small></div><div><small>Label count</small><strong>{datasetClasses.length}</strong><small>BENIGN and 14 attack categories</small></div></div>
      <p><a href={`https://huggingface.co/datasets/${data.model.dataset.id}`} target="_blank" rel="noreferrer">{data.model.dataset.id}</a></p>
      <p className="footnote">Source revision: <code>{data.model.dataset.revision}</code> · Source split: <code>train</code></p>
      <details className="dataset-details" open><summary>Class distribution and attack categories</summary><p>This is the source dataset distribution, not live-network attack prevalence. Labels are preserved verbatim.</p><div className="dataset-table-wrap"><table><thead><tr><th>Label</th><th>Records</th><th>Share</th><th>Distribution</th></tr></thead><tbody>{datasetClasses.map(row => <tr key={row.Label}><td>{row.Label}</td><td>{formatNumber(Number(row.count))}</td><td>{percent(Number(row.percent) / 100)}</td><td><div className="class-share" role="img" aria-label={`${row.Label}: ${percent(Number(row.percent) / 100)}`}><i style={{ width: `${row.percent}%` }} /></div></td></tr>)}</tbody></table></div></details>
      <Source paths={['reports/dataset/provenance.json', 'reports/dataset/classes.csv']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-1">Data preparation</h2>
      <p>Nonnumeric, NaN, infinite and negative measurements were marked null, not imputed as zero. Labels, zeroes and large finite values were preserved. Duplicates were grouped into partitions rather than deleted.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Operation / finding</th><th>Record count</th></tr></thead><tbody>
        <tr><td>Cleaned records</td><td>{formatNumber(preparation.cleaned_rows)}</td></tr><tr><td>Fuzzy-ready records</td><td>{formatNumber(preparation.fuzzy_rows)}</td></tr><tr><td>Excluded from inference due to unavailable inputs</td><td>{formatNumber(preparation.excluded_fuzzy_rows)}</td></tr>
        <tr><td>Source records with missing values</td><td>{formatNumber(quality.missing_rows)}</td></tr><tr><td>Source records with infinite values</td><td>{formatNumber(quality.infinite_rows)}</td></tr><tr><td>Exact duplicates beyond the first occurrence</td><td>{formatNumber(quality.exact_duplicates_excess)}</td></tr>
      </tbody></table></div>
      <p className="footnote">Quality counts can overlap. Cleaned output retains every source record; only records with all five required inputs available enter fuzzy-ready output.</p>
      <details className="dataset-details"><summary>Partitioning and sampling</summary><div className="dataset-table-wrap"><table><thead><tr><th>Original quality-eligible partition</th><th>Records</th></tr></thead><tbody>{Object.entries(preparation.partition_counts).map(([key, count]) => <tr key={key}><td>{key === 'train' ? 'Training' : key === 'validation' ? 'Validation' : 'Test'}</td><td>{formatNumber(count)}</td></tr>)}</tbody></table></div>
        <p>The initial development sample contains {formatNumber(preparation.development_rows)} records; it uses class quotas and does not preserve source prevalence. Seed: <code>{preparation.seed}</code>. Observation groups shared across partitions in the initial manifest: {preparation.groups_crossing_partitions}.</p>
        <p>Later development excluded exposed test records and linked groups: 2,529,845 records excluded, 297,916 eligible. A 60,000-record sample reserved 14,042 design records; 45,958 comparison records rotated through three group-disjoint training/calibration/assessment roles.</p>
        <p>These folds were reused in subsequent experiments. Group disjointness does not establish near-duplicate or session independence; there is no untouched independent-test claim.</p>
      </details><Source paths={['reports/dataset/preprocessing.json', 'reports/dataset/quality.json', 'reports/fuzzy/task02b/evaluation_integrity.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-2">Model architecture</h2><p>The model is a rule-based Mamdani fuzzy inference system, not a conventional machine-learning classifier. Membership boundaries use initial training-partition summaries and network semantics.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Input</th><th>Source column name</th><th>Unit</th><th>Transform</th></tr></thead><tbody>{data.model.features.map(feature => <tr key={feature.key}><td>{feature.title}</td><td><code>{feature.column}</code></td><td>{feature.unit}</td><td>{feature.transform}</td></tr>)}</tbody></table></div>
      <dl className="dataset-definition-list"><div><dt>Rule count</dt><dd>{data.model.rule_count}</dd></div><div><dt>Memberships</dt><dd>Triangular and trapezoidal</dd></div><div><dt>AND / OR</dt><dd>Minimum / maximum</dd></div><div><dt>Implication / aggregation</dt><dd>Minimum clipping / maximum</dd></div><div><dt>Defuzzification</dt><dd>Centroid · {production.output.grid_points} points</dd></div><div><dt>Risk category boundaries</dt><dd>{data.model.risk_category_cuts.join(' / ')}</dd></div></dl>
      <p>Rate, forward count and backward length variation use log1p; the other two inputs are linear. Extreme finite values saturate at the frozen membership domain. Labels are not inference inputs; scores are not attack probabilities.</p>
      <details className="dataset-details"><summary>Configured membership curves</summary><div className="membership-grid">{data.model.features.map(feature => <div className="membership-box" key={feature.key}><h3>{feature.title}</h3><MembershipChart feature={feature} /><div className="output-legend">{feature.chart.curves.map(curve => <span key={curve.term}>{curve.title}</span>)}</div><small className="axis-note">{feature.chart.axis_label}</small></div>)}</div></details>
      <Source paths={['config/fuzzy/task04/selected_v4.json', 'reports/fuzzy/fuzzy_system_design.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-3">Model development</h2><p>The original five-input, 22-rule system was retained. Training-only membership refits, signature weighting and limited rule refinements did not pass the promotion criterion.</p>
      {data.evaluation.optimization && <details className="dataset-details"><summary>Recorded model comparison</summary><p className="footnote">Group-weighted rates · balanced policy · recorded results</p><div className="rule-list">{data.evaluation.optimization.candidates.map(c => <div className="rule-row" key={c.id}><span className="rule-id">{c.id.split('_')[0]}</span><div className="rule-description"><p>{c.id}</p><small>Recall {percent(c.recall)} · FPR {percent(c.fpr)} · ROC-AUC {formatFixed(c.roc_auc, 4)}</small></div><div className="rule-strength"><b>{percent(c.balanced_accuracy)}</b><small>BA ± {percent(c.balanced_accuracy_fold_sd)} fold SD</small></div></div>)}</div></details>}
      <h3>Alternative architectures</h3><p>An eight-input flat model, a four-subsystem hierarchy and three behavior modules were compared within the same eligible development framework.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Architecture</th><th>Rules</th><th>Precision</th><th>Recall</th><th>F1</th><th>FPR</th><th>ROC-AUC</th></tr></thead><tbody>{architectureResults.map(row => <tr key={row.candidate}><td>{row.candidate}</td><td>{row.rules}</td><td>{percent(Number(row.precision))}</td><td>{percent(Number(row.recall))}</td><td>{formatFixed(Number(row.f1), 4)}</td><td>{percent(Number(row.false_positive_rate))}</td><td>{formatFixed(Number(row.roc_auc), 4)}</td></tr>)}</tbody></table></div>
      <p className="footnote">The table shows signature-group-weighted three-fold means for the Balanced policy, not independent testing. Its weighting differs from raw flow confusion counts.</p>
      <p>Despite higher internal recall, the hierarchical candidate's recall fell to zero in Tuesday/Wednesday day stress checks. No alternative passed day stability and none replaced the active model.</p>
      <Source paths={['reports/fuzzy/task04/scientific_report.md', 'reports/fuzzy/task05/comparison.csv', 'reports/fuzzy/task05/final_report.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-4">Calibration</h2><p>Alert thresholds were selected on a separate calibration group using signature-group-weighted FPR targets. The active policy artifact uses calibration bucket 1; thresholds were not tuned on test results. Category boundaries and alert thresholds differ.</p>
      {aligned ? <div className="dataset-table-wrap"><table><thead><tr><th>Policy</th><th>Active threshold</th><th>FPR target</th><th>Calibration FPR</th><th>Calibration recall</th></tr></thead><tbody>{data.policies.map(policy => <tr key={policy.id}><td>{policy.title}</td><td title={String(policy.threshold)}>{formatFixed(policy.threshold, 6)}</td><td>{percent(calibration.policies[policy.id].fpr_cap)}</td><td>{percent(calibration.policies[policy.id].calibration_fpr)}</td><td>{percent(calibration.policies[policy.id].calibration_recall)}</td></tr>)}</tbody></table></div> : <p role="status">The calibration artifact does not match the active model identity.</p>}
      <p className="footnote">FPR targets are not guarantees for live traffic. Policies apply different alert thresholds to the same fuzzy score.</p><Source paths={['config/fuzzy/task04/selected_policies.json', 'reports/fuzzy/task02b/evaluation_integrity.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-5">Evaluation</h2><p>BENIGN is negative and other source labels are positive for evaluation. These labels are not attack severity or calibrated risk levels.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Recorded scenario</th><th>Precision</th><th>Recall</th><th>F1</th><th>FPR</th><th>ROC-AUC</th></tr></thead><tbody>{data.evaluation.historical.map(record => <tr key={record.id}><td>{record.id === 'grouped' ? 'Original grouped test' : 'Original day-based test'}</td><td>{percent(record.metrics.precision)}</td><td>{percent(record.metrics.recall)}</td><td>{formatFixed(record.metrics.f1, 6)}</td><td>{percent(record.metrics.false_positive_rate)}</td><td>{formatFixed(record.metrics.roc_auc, 6)}</td></tr>)}</tbody></table></div>
      <p>The original grouped test contains 150 BENIGN and 1,600 attack records, not source prevalence. Day-based evaluation used Monday–Wednesday training, Thursday calibration and Friday testing; Friday attack categories were absent from training. These are previously exposed historical results.</p>
      <p>Later internal validation used rotating group-disjoint roles and separate calibration thresholds. Frozen-model overlap with historical training and adaptive fold reuse limit independent generalization claims.</p><a className="text-button" href="#evaluation">Return to Model Performance</a>
      <Source paths={['reports/fuzzy/metrics.json', 'reports/fuzzy/task02b/evaluation_integrity.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-6">Limitations</h2><ul className="dataset-limitations"><li>Dataset/scenario shift, source imbalance and near-duplicate dependence remain; grouping does not remove all dependencies.</li><li>Live features use a versioned CIC compatibility hypothesis; exact equivalence to the original exporter and reference PCAPs is unverified.</li><li>Capture loss, offload, missing flow beginnings and timeout differences can alter measurements.</li><li>Independent live attack-detection accuracy is not established. Rare categories, particularly 11 Heartbleed records, cannot support reliable class-performance claims.</li></ul><Source paths={['docs/realtime-monitoring.md', 'reports/fuzzy/task05/final_report.md']} />
    </Card>
  </div>)
}
