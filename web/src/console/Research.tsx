import { useState } from 'react'
import type { AppData, Example, PolicyID } from '../types'
import { Membership } from './Evidence'
import { useLabels, useRuleText, useWord } from './language'
import classes from '../../../reports/dataset/classes.csv?raw'
import { summary } from '../../../reports/fuzzy/accuracy-study/metrics.json'

const classRows = classes.trim().split(/\r?\n/).slice(1).map(line => {
  const [label, count, share] = line.split(',')
  return { label, count: Number(count), share: Number(share) }
})
const researchRows = ['frozen/deployed', 'frozen/always_benign', 'hierarchy/raw', 'hierarchy/balanced'] as const

export function Records({ data, open }: { data: AppData; open: (example: Example) => void }) {
  const { t, n } = useLabels()
  const w = useWord()
  const [filter, setFilter] = useState('')
  const examples = data.examples.filter(example => !filter || (filter === 'errors'
    ? (example.dataset_label !== 'BENIGN') !== example.alert
    : (example.dataset_label === 'BENIGN') === (filter === 'benign')))
  return <>
    <div className="page-heading"><div><h1>{t('Recorded traffic', 'Kayıtlı trafik')}</h1><p>{t('Curated flows with source labels and recorded policy decisions.', 'Kaynak etiketleri ve kayıtlı politika kararlarıyla seçilmiş akışlar.')}</p></div>
      <select value={filter} onChange={e => setFilter(e.target.value)} aria-label={t('Record filter', 'Kayıt filtresi')}>
        <option value="">{t('All records', 'Tüm kayıtlar')}</option><option value="benign">BENIGN</option><option value="attack">{t('Attack-labeled', 'Saldırı etiketli')}</option><option value="errors">{t('Incorrect decisions', 'Hatalı kararlar')}</option>
      </select></div>
    <div className="surface table-scroll"><table><thead><tr><th>{t('Record', 'Kayıt')}</th><th>{t('Source label', 'Kaynak etiketi')}</th><th>{t('Risk score', 'Risk puanı')}</th><th>{t('Recorded decision', 'Kayıtlı karar')}</th><th>{t('Analysis', 'Analiz')}</th></tr></thead>
      <tbody>{examples.map(item => <tr key={item.id}>
        <td><strong>{item.title}</strong><small>#{item.source_row_id} · {item.source_day}</small></td><td>{item.dataset_label}</td>
        <td data-risk={item.risk_level}>{n(item.risk_score)} · {w(item.risk_level)}</td>
        <td>{item.alert ? t('Alert', 'Alarm') : t('No alert', 'Alarm yok')}<small>{w(item.reference_policy)}</small></td>
        <td><button className="button" onClick={() => open(item)}>{t('Analyze', 'Analiz et')}</button></td>
      </tr>)}</tbody></table>
      {!examples.length && <p className="empty">{t('No records match the filter.', 'Filtreye uygun kayıt yok.')}</p>}
    </div>
  </>
}

export function Performance({ data }: { data: AppData }) {
  const { t, n } = useLabels()
  const w = useWord()
  const [scenario, setScenario] = useState('internal')
  const [policy, setPolicy] = useState<PolicyID>('Balanced')
  const historical = data.evaluation.historical.find(row => row.id === scenario)
  const internal = data.evaluation.internal.find(row => row.id === policy)
  const entry = historical ?? internal
  const names: Record<string, string> = { grouped: t('Historical grouped', 'Tarihsel gruplu'), day: t('Historical by day', 'Gün bazlı tarihsel'), internal: t('Internal validation', 'İç doğrulama') }
  const percent = (value: number) => n(value * 100, 3) + '%'
  return <>
    <div className="page-heading"><div><h1>{t('Model performance', 'Model performansı')}</h1><p>{t('Offline evaluation of recorded data.', 'Kayıtlı verilerle çevrimdışı değerlendirme.')}</p></div></div>
    <div className="actions scenario">{['internal', ...data.evaluation.historical.map(row => row.id)].map(id => <button className="button" key={id} aria-pressed={scenario === id} onClick={() => setScenario(id)}>{names[id] ?? id}</button>)}</div>
    <div className="surface study-panel">
      <header className="section-head"><div><h2>{names[scenario] ?? scenario}</h2><p>{historical ? t('Historical test · individual flows', 'Tarihsel test · tekil akışlar') : t('Reused development data · group-weighted fold means', 'Yeniden kullanılan geliştirme verisi · grup ağırlıklı kat ortalamaları')}</p></div>
        {!historical && <select aria-label={t('Recorded policy', 'Kayıtlı politika')} value={policy} onChange={e => setPolicy(e.target.value as PolicyID)}>{data.policies.map(item => <option key={item.id} value={item.id}>{w(item.title)}</option>)}</select>}</header>
      {entry && <>
        <div className="stat-grid">{[
          [t('Attack recall', 'Saldırı duyarlılığı'), percent(entry.metrics.recall)],
          [t('False positive rate', 'Yanlış pozitif oranı'), percent(entry.metrics.false_positive_rate)],
          [t('Balanced accuracy', 'Dengeli doğruluk'), percent(entry.metrics.balanced_accuracy)],
          [t('Precision', 'Kesinlik'), percent(entry.metrics.precision)],
          ['F1', n(entry.metrics.f1, 4)], ['ROC-AUC', n(entry.metrics.roc_auc, 4)],
        ].map(([label, value]) => <div key={label}><small>{label}</small><strong>{value}</strong></div>)}</div>
        <h3>{t('Confusion matrix · raw flows', 'Karışıklık matrisi · ham akışlar')}</h3>
        <table className="matrix-new"><thead><tr><th>{t('Label', 'Etiket')}</th><th>{t('No alert', 'Alarm yok')}</th><th>{t('Alert', 'Alarm')}</th></tr></thead>
          <tbody><tr><th>BENIGN</th><td>{n(entry.confusion.tn)}</td><td>{n(entry.confusion.fp)}</td></tr>
            <tr><th>{t('Attack', 'Saldırı')}</th><td>{n(entry.confusion.fn)}</td><td>{n(entry.confusion.tp)}</td></tr></tbody></table>
        {!historical && <p className="quiet">{t('The raw flow matrix and group-weighted rates have different aggregation rules.', 'Ham akış matrisi ile grup ağırlıklı oranlar farklı yöntemlerle hesaplanır.')}</p>}
      </>}
    </div>
    <section className="surface study-panel"><h2>{t('Accuracy study', 'Doğruluk araştırması')}</h2><p className="quiet">{t('Reused internal evaluation · 45,958 flows', 'Yeniden kullanılan iç değerlendirme · 45.958 akış')}</p>
      <div className="table-scroll"><table><thead><tr><th>{t('Configuration', 'Yapılandırma')}</th><th>{t('Raw accuracy', 'Ham doğruluk')}</th><th>{t('Group balanced accuracy', 'Grup dengeli doğruluk')}</th><th>{t('Group recall', 'Grup duyarlılığı')}</th><th>{t('Group FPR', 'Grup YPO')}</th></tr></thead>
        <tbody>{researchRows.map((key, i) => {
          const { pooled_raw_confusion: c, group_fold_mean: m } = summary[key]
          const labels = [t('Active model and threshold', 'Etkin model ve eşik'), t('Always benign', 'Her akışı normal say'), t('Hierarchy · raw accuracy', 'Hiyerarşi · ham doğruluk'), t('Hierarchy · balanced accuracy', 'Hiyerarşi · dengeli doğruluk')]
          return <tr key={key}><th scope="row">{labels[i]}</th><td>{percent((c.tn + c.tp) / (c.tn + c.tp + c.fp + c.fn))}</td><td>{percent(m.balanced_accuracy)}</td><td>{percent(m.recall)}</td><td>{percent(m.false_positive_rate)}</td></tr>
        })}</tbody></table></div>
      <p className="notice">{t('The balanced-accuracy hierarchy detected no attacks in the Tuesday, Wednesday and Thursday stress checks. Independent live detection performance remains unverified.', 'Dengeli doğruluk eşiğiyle hiyerarşi Salı, Çarşamba ve Perşembe sınamalarında saldırı yakalayamadı. Bağımsız canlı tespit başarısı henüz doğrulanmadı.')}</p>
    </section>
  </>
}

export function Reference({ data, dataset }: { data: AppData; dataset: boolean }) {
  const { t, n } = useLabels()
  const w = useWord()
  const ruleText = useRuleText()
  if (dataset) return <>
    <div className="page-heading"><div><h1>{t('Dataset', 'Veri seti')}</h1><p>CIC-IDS2017 · {data.model.dataset.id}</p></div>
      <a className="button" href={`https://huggingface.co/datasets/${data.model.dataset.id}`} target="_blank" rel="noreferrer">{t('View source', 'Kaynağı görüntüle')}</a></div>
    <div className="surface study-panel"><div className="stat-grid">{[[t('Records', 'Kayıt'), data.model.dataset.records], [t('Columns', 'Sütun'), data.model.dataset.columns], [t('Labels', 'Etiket'), data.model.dataset.labels]].map(([label, value]) => <div key={label}><small>{label}</small><strong>{n(Number(value))}</strong></div>)}</div>
      <p className="quiet">{t('Revision', 'Sürüm')} <code>{data.model.dataset.revision}</code></p>
      <h2>{t('Class distribution', 'Sınıf dağılımı')}</h2>
      <div className="table-scroll"><table><thead><tr><th>{t('Label', 'Etiket')}</th><th>{t('Count', 'Adet')}</th><th>{t('Share', 'Pay')}</th></tr></thead><tbody>{classRows.map(row => <tr key={row.label}><th scope="row">{row.label}</th><td>{n(row.count)}</td><td>{n(row.share, 5)}%</td></tr>)}</tbody></table></div>
      <p className="notice">{t('Source dataset labels are used for evaluation. Live extraction can differ from the original exporter because of capture loss and flow boundaries.', 'Kaynak etiketleri değerlendirmede kullanılır. Paket kaybı ve akış sınırları nedeniyle canlı ölçümler özgün dışa aktarıcıdan farklı olabilir.')}</p>
    </div>
  </>
  return <>
    <div className="page-heading"><div><h1>{t('Model reference', 'Model referansı')}</h1><p>{data.model.method} · {data.model.defuzzification}</p></div><a className="button" href="/docs">{t('API reference', 'API referansı')}</a></div>
    <section className="surface study-panel"><dl className="flow-facts"><div><dt>{t('Model', 'Model')}</dt><dd>{data.model.model_version}</dd></div><div><dt>{t('Configuration', 'Yapılandırma')}</dt><dd>{data.model.configuration_version}</dd></div><div><dt>{t('Application', 'Uygulama')}</dt><dd>{data.model.app_version}</dd></div></dl>
      <p className="quiet"><code>{data.model.model_id}</code></p><h2>{t('Membership functions', 'Üyelik fonksiyonları')}</h2>
      <div className="signals">{data.model.features.map(feature => <Membership key={feature.key} feature={feature}/>)}</div></section>
    <section className="surface study-panel"><h2>{t('Rule inventory', 'Kural tabanı')} · {data.model.rule_count}</h2><ol className="rule-lines">{data.model.rules.map(rule => <li key={rule.id}><code>{rule.id}</code><span>{ruleText(rule.text)}</span><span data-risk={rule.consequent}>{w(rule.consequent)}</span></li>)}</ol></section>
  </>
}
