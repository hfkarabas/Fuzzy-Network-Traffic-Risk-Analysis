import { useI18n } from './i18n'
import { formatNumber, formatFixed, locale } from './format'
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
const percent = (value: number) => `${new Intl.NumberFormat(locale(), { maximumFractionDigits: 4 }).format(value * 100)}%`
function Source({ paths }: { paths: string[] }) {
  const { localize } = useI18n()
  return localize(<p className="dataset-source">Kaynak kayıtları: {paths.map(path => <code key={path} data-i18n-skip>{path}</code>)}</p>)
}

export default function DatasetInformation({ data }: { data: AppData }) {
  const { localize } = useI18n()
  const aligned = calibration.model_id === data.model.model_id
  return localize(<div className="dataset-information">
    <div className="page-title"><h1>Veri Seti Bilgileri</h1><p>Veri kaynağı, model geliştirme ve kayıtlı değerlendirme kapsamı</p></div>
    <nav className="dataset-sections" aria-label="Veri bilgisi bölümleri">{['Veri seti', 'Veri hazırlama', 'Model mimarisi', 'Model geliştirme', 'Kalibrasyon', 'Değerlendirme', 'Sınırlamalar'].map((label, i) => <button key={label} onClick={() => document.getElementById(`dataset-section-${i}`)?.scrollIntoView?.({ block: 'start' })}>{label}</button>)}</nav>

    <Card className="dataset-section"><h2 id="dataset-section-0">Veri seti</h2>
      <div className="dataset-facts"><div><small>Kaynak</small><strong data-i18n-skip>CIC-IDS2017</strong></div><div><small>Kayıt sayısı</small><strong>{formatNumber(data.model.dataset.records)}</strong></div><div><small>Kaynak sütunlar</small><strong>{data.model.dataset.columns}</strong><small>78 sayısal alan ve etiket</small></div><div><small>Etiket sayısı</small><strong>{datasetClasses.length}</strong><small>BENIGN ve 14 saldırı kategorisi</small></div></div>
      <p><a href={`https://huggingface.co/datasets/${data.model.dataset.id}`} target="_blank" rel="noreferrer" data-i18n-skip>{data.model.dataset.id}</a></p>
      <p className="footnote">Kaynak revizyonu: <code data-i18n-skip>{data.model.dataset.revision}</code> · Kaynak bölümü: <code data-i18n-skip>train</code></p>
      <details className="dataset-details" open><summary>Sınıf dağılımı ve saldırı kategorileri</summary><p>Kaynak veri dağılımıdır; canlı ağdaki saldırı sıklığını göstermez. Etiketler kaynakta olduğu gibi korunur.</p><div className="dataset-table-wrap"><table><thead><tr><th>Etiket</th><th>Kayıt</th><th>Pay</th><th>Dağılım</th></tr></thead><tbody>{datasetClasses.map(row => <tr key={row.Label}><td data-i18n-skip>{row.Label}</td><td>{formatNumber(Number(row.count))}</td><td>{percent(Number(row.percent) / 100)}</td><td><div className="class-share" role="img" aria-label={`${row.Label}: ${percent(Number(row.percent) / 100)}`}><i style={{ width: `${row.percent}%` }} /></div></td></tr>)}</tbody></table></div></details>
      <Source paths={['reports/dataset/provenance.json', 'reports/dataset/classes.csv']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-1">Veri hazırlama</h2>
      <p>Sayısal olmayan, NaN, sonsuz ve negatif ölçümler null olarak işaretlendi; eksikler sıfırla doldurulmadı. Etiketler, sıfırlar ve büyük sonlu değerler korundu. Kopyalar silinmedi; gruplandırılarak bölümlere atandı.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>İşlem / bulgu</th><th>Kayıt sayısı</th></tr></thead><tbody>
        <tr><td>Temizlenmiş kayıtlar</td><td>{formatNumber(preparation.cleaned_rows)}</td></tr><tr><td>Bulanık çıkarıma uygun kayıtlar</td><td>{formatNumber(preparation.fuzzy_rows)}</td></tr><tr><td>Eksik girdi nedeniyle çıkarım dışında</td><td>{formatNumber(preparation.excluded_fuzzy_rows)}</td></tr>
        <tr><td>Eksik değer içeren kaynak kayıtlar</td><td>{formatNumber(quality.missing_rows)}</td></tr><tr><td>Sonsuz değer içeren kaynak kayıtlar</td><td>{formatNumber(quality.infinite_rows)}</td></tr><tr><td>İlk örnek dışındaki tam kopyalar</td><td>{formatNumber(quality.exact_duplicates_excess)}</td></tr>
      </tbody></table></div>
      <p className="footnote">Kalite sayımları örtüşebilir. Temizlenmiş çıktı tüm kaynak kayıtları korur; yalnızca beş gerekli girdisi kullanılabilir olan kayıtlar bulanık çıktıya girer.</p>
      <details className="dataset-details"><summary>Bölme ve örnekleme</summary><div className="dataset-table-wrap"><table><thead><tr><th>İlk kalite-uygun bölüm</th><th>Kayıt</th></tr></thead><tbody>{Object.entries(preparation.partition_counts).map(([key, count]) => <tr key={key}><td>{key === 'train' ? 'Eğitim' : key === 'validation' ? 'Doğrulama' : 'Test'}</td><td>{formatNumber(count)}</td></tr>)}</tbody></table></div>
        <p>İlk geliştirme örneği {formatNumber(preparation.development_rows)} kayıttır; sınıf kotalıdır ve kaynak dağılımını korumaz. Tohum: <code>{preparation.seed}</code>. İlk manifestte bölümler arasında ortak gözlem grubu: {preparation.groups_crossing_partitions}.</p>
        <p>Sonraki geliştirmede açığa çıkmış test kayıtları ve bağlantılı gruplar dışlandı: 2.529.845 kayıt çıkarıldı, 297.916 kayıt uygun kaldı. Bu nüfustan 60.000 kayıt seçildi; 14.042 tasarım kaydı ayrıldı, 45.958 karşılaştırma kaydı üç grup-ayrık eğitim/kalibrasyon/değerlendirme rolünde döndürüldü.</p>
        <p>Bu katlar sonraki denemelerde yeniden kullanıldı. Grup ayrılığı, yakın kopya veya oturum bağımsızlığını kanıtlamaz; dokunulmamış bağımsız test iddiası yoktur.</p>
      </details><Source paths={['reports/dataset/preprocessing.json', 'reports/dataset/quality.json', 'reports/fuzzy/task02b/evaluation_integrity.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-2">Model mimarisi</h2><p>Model, kural tabanlı Mamdani bulanık çıkarım sistemidir; geleneksel bir makine öğrenmesi sınıflandırıcısı değildir. Üyelik sınırları ilk eğitim grubunun dağılım özetleri ve ağ anlamı kullanılarak belirlenmiştir.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Girdi</th><th>Kaynak sütun adı</th><th>Birim</th><th>Dönüşüm</th></tr></thead><tbody>{data.model.features.map(feature => <tr key={feature.key}><td>{feature.title}</td><td><code data-i18n-skip>{feature.column}</code></td><td>{feature.unit}</td><td data-i18n-skip>{feature.transform}</td></tr>)}</tbody></table></div>
      <dl className="dataset-definition-list"><div><dt>Kural sayısı</dt><dd>{data.model.rule_count}</dd></div><div><dt>Üyelikler</dt><dd>Üçgen ve yamuk</dd></div><div><dt>AND / OR</dt><dd>Minimum / maksimum</dd></div><div><dt>İmplikasyon / birleştirme</dt><dd>Minimum kırpma / maksimum</dd></div><div><dt>Durulaştırma</dt><dd>Ağırlık merkezi · {production.output.grid_points} nokta</dd></div><div><dt>Risk kategorisi sınırları</dt><dd>{data.model.risk_category_cuts.join(' / ')}</dd></div></dl>
      <p>Hız, ileri paket sayısı ve geri boyut değişkenliği log1p ile dönüştürülür; diğer iki girdi doğrusaldır. Sonlu uç değerler sabit üyelik alanında doyurulur. Etiketler çıkarım girdisi değildir; risk puanı saldırı olasılığı değildir.</p>
      <details className="dataset-details"><summary>Yapılandırılmış üyelik eğrileri</summary><div className="membership-grid">{data.model.features.map(feature => <div className="membership-box" key={feature.key}><h3>{feature.title}</h3><MembershipChart feature={feature} /><div className="output-legend">{feature.chart.curves.map(curve => <span key={curve.term}>{curve.title}</span>)}</div><small className="axis-note">{feature.chart.axis_label}</small></div>)}</div></details>
      <Source paths={['config/fuzzy/task04/selected_v4.json', 'reports/fuzzy/fuzzy_system_design.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-3">Model geliştirme</h2><p>İlk beş girdili, 22 kurallı yapı korunmuştur. Eğitim grubunda yeniden üyelik belirleme, imza-grubu ağırlıkları ve sınırlı kural değişiklikleri terfi ölçütünü geçmedi.</p>
      {data.evaluation.optimization && <details className="dataset-details"><summary>Kayıtlı model karşılaştırması</summary><p className="footnote">Grup ağırlıklı oranlar · dengeli politika · kaydedilmiş sonuçlar</p><div className="rule-list">{data.evaluation.optimization.candidates.map(c => <div className="rule-row" key={c.id}><span className="rule-id">{c.id.split('_')[0]}</span><div className="rule-description"><p>{c.id}</p><small>Duyarlılık {percent(c.recall)} · FPR {percent(c.fpr)} · ROC-AUC {formatFixed(c.roc_auc, 4)}</small></div><div className="rule-strength"><b>{percent(c.balanced_accuracy)}</b><small>BA ± {percent(c.balanced_accuracy_fold_sd)} kat SS</small></div></div>)}</div></details>}
      <h3>Alternatif mimariler</h3><p>Sekiz girdili düz model, dört alt sistemli hiyerarşi ve üç davranış modüllü yapı aynı uygun geliştirme çerçevesinde karşılaştırıldı.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Mimari</th><th>Kurallar</th><th>Kesinlik</th><th>Duyarlılık</th><th>F1</th><th>FPR</th><th>ROC-AUC</th></tr></thead><tbody>{architectureResults.map(row => <tr key={row.candidate}><td data-i18n-skip>{row.candidate}</td><td>{row.rules}</td><td>{percent(Number(row.precision))}</td><td>{percent(Number(row.recall))}</td><td>{formatFixed(Number(row.f1), 4)}</td><td>{percent(Number(row.false_positive_rate))}</td><td>{formatFixed(Number(row.roc_auc), 4)}</td></tr>)}</tbody></table></div>
      <p className="footnote">Tablo, dengeli politikanın üç kattaki imza-grubu ağırlıklı ortalamasıdır; bağımsız test değildir. Ham akış matrisiyle aynı ağırlıklandırmayı kullanmaz.</p>
      <p>Hiyerarşik adayın duyarlılığı daha yüksek olsa da Salı/Çarşamba gün sınamalarında sıfıra düştü. Gün kararlılığı ölçütü sağlanmadığından hiçbir alternatif aktif modele alınmadı.</p>
      <Source paths={['reports/fuzzy/task04/scientific_report.md', 'reports/fuzzy/task05/comparison.csv', 'reports/fuzzy/task05/final_report.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-4">Kalibrasyon</h2><p>Alarm eşikleri ayrı kalibrasyon grubunda, imza-grubu ağırlıklı FPR hedefleriyle seçildi. Aktif politika kaydı kalibrasyon kovası 1 kullanır; test sonuçlarına göre eşik ayarlanmadı. Kategori sınırları ile alarm eşikleri farklıdır.</p>
      {aligned ? <div className="dataset-table-wrap"><table><thead><tr><th>Politika</th><th>Aktif eşik</th><th>FPR hedefi</th><th>Kalibrasyon FPR</th><th>Kalibrasyon duyarlılığı</th></tr></thead><tbody>{data.policies.map(policy => <tr key={policy.id}><td>{policy.title}</td><td title={String(policy.threshold)}>{formatFixed(policy.threshold, 6)}</td><td>{percent(calibration.policies[policy.id].fpr_cap)}</td><td>{percent(calibration.policies[policy.id].calibration_fpr)}</td><td>{percent(calibration.policies[policy.id].calibration_recall)}</td></tr>)}</tbody></table></div> : <p role="status">Kalibrasyon kaydı aktif model kimliğiyle eşleşmiyor.</p>}
      <p className="footnote">FPR hedefleri canlı trafik için garanti değildir. Politika değişimi aynı bulanık puana farklı alarm eşiği uygular.</p><Source paths={['config/fuzzy/task04/selected_policies.json', 'reports/fuzzy/task02b/evaluation_integrity.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-5">Değerlendirme</h2><p>BENIGN negatif, diğer kaynak etiketleri pozitif kabul edilir. Bunlar saldırı şiddeti veya kalibre edilmiş risk seviyeleri değildir.</p>
      <div className="dataset-table-wrap"><table><thead><tr><th>Kayıtlı senaryo</th><th>Kesinlik</th><th>Duyarlılık</th><th>F1</th><th>FPR</th><th>ROC-AUC</th></tr></thead><tbody>{data.evaluation.historical.map(record => <tr key={record.id}><td>{record.id === 'grouped' ? 'İlk gruplu test' : 'İlk gün bazlı test'}</td><td>{percent(record.metrics.precision)}</td><td>{percent(record.metrics.recall)}</td><td>{formatFixed(record.metrics.f1, 6)}</td><td>{percent(record.metrics.false_positive_rate)}</td><td>{formatFixed(record.metrics.roc_auc, 6)}</td></tr>)}</tbody></table></div>
      <p>İlk gruplu testte 150 BENIGN ve 1.600 saldırı kaydı bulunur; kaynak dağılımını temsil etmez. Gün bazlı değerlendirmede Pazartesi–Çarşamba eğitim, Perşembe kalibrasyon ve Cuma test kullanıldı; Cuma saldırı türleri eğitimde yoktu. Bu testler daha önce incelenmiş tarihsel kanıttır.</p>
      <p>Sonraki iç doğrulama, grup-ayrık dönen roller ve ayrı kalibrasyon eşikleri kullandı. Aktif dondurulmuş modelin eski eğitim verileriyle örtüşmesi ve katların yeniden kullanımı bağımsız genelleme iddiasını sınırlar.</p><a className="text-button" href="#evaluation">Model Performansı ekranına dön</a>
      <Source paths={['reports/fuzzy/metrics.json', 'reports/fuzzy/task02b/evaluation_integrity.md']} />
    </Card>

    <Card className="dataset-section"><h2 id="dataset-section-6">Sınırlamalar</h2><ul className="dataset-limitations"><li>Veri/senaryo kayması, kaynak dengesizliği ve yakın kopya bağımlılığı sürer; grup ayrılığı tüm bağımlılıkları kaldırmaz.</li><li>Canlı özellikler sürümlenmiş CIC uyumluluk varsayımına dayanır; özgün dışa aktarıcı ve referans PCAP ile tam eşdeğerlik doğrulanmamıştır.</li><li>Yakalama kaybı, offload, eksik akış başlangıcı ve zaman aşımı farklılıkları ölçümleri değiştirebilir.</li><li>Bağımsız canlı saldırı tespit doğruluğu gösterilmemiştir. Az örnekli sınıflar, özellikle 11 Heartbleed kaydı, güvenilir sınıf başarısı iddiası sağlamaz.</li></ul><Source paths={['docs/realtime-monitoring.md', 'reports/fuzzy/task05/final_report.md']} />
    </Card>
  </div>)
}
