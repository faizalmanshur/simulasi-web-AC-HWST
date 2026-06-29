import { useEffect, useMemo, useState } from 'react'

type Config = Record<string, number | string>
type FieldDef = [string, string, string, string]
type InputGroup = { id: string; title: string; fields: FieldDef[] }
type SummaryRow = { output: string; value: string | number | null; unit: string }
type TimeRow = Record<string, number | string | boolean | null>
type CoilUsageRow = {
  sistem?: string
  komponen: string
  zona: string
  persentase_COP_best_DSH?: number
  persentase_akhir?: number
  persentase_steady?: number
  t_COP_best_DSH_min?: number
  T_tank_COP_best_DSH_C?: number
  catatan: string
}
type PhPoint = { label: string; name: string; h_kJ_kg: number; P_kPa: number; T_C: number }
type PhFrame = { time_min: number; points: PhPoint[] }
type PhDome = { liquid: Array<{ h_kJ_kg: number; P_kPa: number; T_C: number }>; vapor: Array<{ h_kJ_kg: number; P_kPa: number; T_C: number }>; source: string }
type SimulationResults = {
  status: string
  summary_values: Record<string, number | string | null>
  summary_rows: SummaryRow[]
  time_series: TimeRow[]
  visualization_series?: TimeRow[]
  ph_series?: PhFrame[]
  ph_conventional?: PhFrame
  ph_dome?: PhDome
  coil_usage: CoilUsageRow[]
  coil_usage_conventional?: CoilUsageRow[]
  state_rows: Array<Record<string, string | number>>
  geometry_rows: Array<Record<string, string | number>>
  analysis_rows: Array<Record<string, string | number>>
  validation_rows?: Array<Record<string, string | number | null>>
  condition_rows?: Array<Record<string, string | number | null>>
  pressure_drop_rows?: Array<Record<string, string | number | null>>
  heat_transfer_rows?: Array<Record<string, string | number | null>>
  assumption_rows?: Array<Record<string, string | number | null>>
  volume_variation?: Array<Record<string, string | number | null>>
  config: Config
}

type Page = 'dashboard' | 'visualisasi' | 'ph'
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? `http://${window.location.hostname}:8000`
const numberKeys = new Set<string>()

function normalizeConfigForApi(cfg: Config, defaults: Config = {}): Config {
  const out: Config = {}
  Object.entries(cfg).forEach(([key, value]) => {
    if (numberKeys.has(key)) {
      const raw = String(value ?? '').trim().replace(',', '.')
      const isTransient = raw === '' || raw === '-' || raw === '+' || raw === '.' || raw === ',' || raw === '-.' || raw === '+.'
      const parsed = Number(raw)
      if (!isTransient && Number.isFinite(parsed)) {
        out[key] = parsed
      } else {
        // Jika field sedang kosong / belum selesai diketik, jangan kirim angka aneh ke backend.
        // Pakai default awal agar simulasi tidak tiba-tiba memakai 0 atau nilai minus karena input HTML.
        const fallbackRaw = String(defaults[key] ?? '').trim().replace(',', '.')
        const fallback = Number(fallbackRaw)
        out[key] = Number.isFinite(fallback) ? fallback : raw
      }
    } else {
      out[key] = value
    }
  })
  return out
}

function numericMode(config: Config, key: string): number {
  const value = config[key]
  const n = Number(String(value ?? '').replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

function isFieldVisible(key: string, config: Config): boolean {
  const capMode = numericMode(config, 'capillary_mode') || 2
  if (key === 'capillary_D_i_mm') return capMode === 1 || capMode === 2
  if (key === 'capillary_length_m') return capMode === 1 || capMode === 3
  return true
}

function App() {
  const [config, setConfig] = useState<Config>({})
  const [defaultConfig, setDefaultConfig] = useState<Config>({})
  const [groups, setGroups] = useState<InputGroup[]>([])
  const [activeGroup, setActiveGroup] = useState<string>('ac')
  const [results, setResults] = useState<SimulationResults | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('Memuat input default...')
  const [page, setPage] = useState<Page>('dashboard')

  useEffect(() => {
    async function fetchDefaults() {
      try {
        const response = await fetch(`${API_BASE}/api/default-inputs`)
        if (!response.ok) throw new Error('Gagal mengambil input default dari backend')
        const data = await response.json()
        setConfig(data.config)
        setDefaultConfig(data.config)
        setGroups(data.groups)
        numberKeys.clear()
        data.groups.forEach((group: InputGroup) => {
          group.fields.forEach(([key]) => {
            if (typeof data.config[key] === 'number') numberKeys.add(key)
          })
        })
        setActiveGroup(data.groups?.[0]?.id ?? 'ac')
        setMessage('Backend aktif. Input default berhasil dimuat.')
      } catch (error) {
        setMessage(error instanceof Error ? error.message : 'Backend belum aktif')
      }
    }
    fetchDefaults()
  }, [])

  const activeFields = useMemo(() => groups.find((group) => group.id === activeGroup)?.fields ?? [], [groups, activeGroup])
  const visibleFields = useMemo(() => activeFields.filter(([key]) => isFieldVisible(key, config)), [activeFields, config])

  const handleChange = (key: string, value: string) => {
    // Simpan nilai sebagai teks selama user mengetik.
    // Ini mencegah bug input desimal seperti "1." menjadi "1" atau field kosong berubah jadi 0.
    // Konversi angka baru dilakukan saat Run/Export.
    setConfig((prev) => ({ ...prev, [key]: value }))
  }

  const runSimulation = async () => {
    setLoading(true)
    setMessage('Simulasi sedang berjalan...')
    try {
      const response = await fetch(`${API_BASE}/api/run-simulation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: normalizeConfigForApi(config, defaultConfig) }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Simulasi gagal')
      setResults(data)
      setMessage('Simulasi selesai. Visualisasi dan diagram P-h sudah siap.')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Simulasi gagal')
    } finally {
      setLoading(false)
    }
  }

  const resetInput = async () => {
    setResults(null)
    setMessage('Memuat ulang input default...')
    const response = await fetch(`${API_BASE}/api/default-inputs`)
    const data = await response.json()
    setConfig(data.config)
    setDefaultConfig(data.config)
    setGroups(data.groups)
    numberKeys.clear()
    data.groups.forEach((group: InputGroup) => {
      group.fields.forEach(([key]) => {
        if (typeof data.config[key] === 'number') numberKeys.add(key)
      })
    })
    setMessage('Input berhasil di-reset.')
  }

  const downloadExport = async (type: 'excel' | 'pdf') => {
    setMessage(`Membuat file ${type.toUpperCase()}...`)
    try {
      const endpoint = type === 'excel' ? 'export-excel' : 'export-pdf'
      const response = await fetch(`${API_BASE}/api/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: normalizeConfigForApi(config, defaultConfig), results }),
      })
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Export gagal')
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = type === 'excel' ? 'laporan_simulasi_hwst.xlsx' : 'laporan_simulasi_hwst.pdf'
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setMessage(`Export ${type.toUpperCase()} selesai.`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Export gagal')
    }
  }

  const summary = results?.summary_values ?? {}

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Dashboard Simulasi Berbasis Web</p>
          <h1>Simulasi AC + Hot Water Storage Tank</h1>
          <p className="hero-text">Tugas akhir simulasi numerik Faiz al 'manshur</p>
          <nav className="page-nav page-nav-with-report">
            <button className={page === 'dashboard' ? 'nav-active' : ''} onClick={() => setPage('dashboard')}>Dashboard</button>
            <button className={page === 'visualisasi' ? 'nav-active' : ''} onClick={() => setPage('visualisasi')}>Visualisasi Sistem</button>
            <button className={page === 'ph' ? 'nav-active' : ''} onClick={() => setPage('ph')}>Diagram P-h</button>
            <span className="nav-divider" aria-hidden="true" />
            <button className="report-nav-btn" onClick={() => downloadExport('excel')} disabled={!results}>Report Excel</button>
            <button className="report-nav-btn" onClick={() => downloadExport('pdf')} disabled={!results}>Report PDF</button>
          </nav>
        </div>
        <div className="status-box">
          <span>Status</span>
          <strong>{loading ? 'Running...' : results ? results.status : 'Standby'}</strong>
          <small>{message}</small>
        </div>
      </section>

      {page === 'dashboard' && (
        <section className="layout">
          <aside className="panel input-panel">
            <div className="panel-title">
              <h2>Input Simulasi</h2>
              <p>Pilih kategori lalu ubah nilai parameter.</p>
            </div>
            <div className="tabs">
              {groups.map((group) => (
                <button key={group.id} className={activeGroup === group.id ? 'tab active' : 'tab'} onClick={() => setActiveGroup(group.id)}>{group.title}</button>
              ))}
            </div>
            <div className="form-grid">
              {visibleFields.map(([key, label, unit, note]) => (
                <label className="field" key={key}>
                  <span>{label}</span>
                  <div className="input-row">
                    {key === 'refrigerant' ? (
                      <select value={String(config[key] ?? '')} onChange={(e) => handleChange(key, e.target.value)}>
                        <option value="R32">R32</option><option value="R410A">R410A</option><option value="R22">R22</option><option value="R134a">R134a</option>
                      </select>
                    ) : key === 'calculation_method' ? (
                      <select value={String(config[key] ?? '2')} onChange={(e) => handleChange(key, e.target.value)}>
                        <option value="1">Segmented UA–ΔT</option>
                        <option value="2">NTU–Effectiveness Zona</option>
                      </select>
                    ) : key === 'pressure_drop_feedback' ? (
                      <select value={String(config[key] ?? '0')} onChange={(e) => handleChange(key, e.target.value)}>
                        <option value="0">Diagnostic only</option>
                        <option value="1">Feedback tekanan jika DP wajar</option>
                      </select>
                    ) : key === 'capillary_mode' ? (
                      <select value={String(config[key] ?? '2')} onChange={(e) => handleChange(key, e.target.value)}>
                        <option value="1">Geometri aktual: D + L</option>
                        <option value="2">Iterasi panjang dari diameter</option>
                        <option value="3">Iterasi diameter dari panjang</option>
                        <option value="4">Auto-search D + L</option>
                      </select>
                    ) : key === 'evaporator_air_model' ? (
                      <select value={String(config[key] ?? '2')} onChange={(e) => handleChange(key, e.target.value)}>
                        <option value="1">Manual SHR</option>
                        <option value="2">Psikrometrik RH</option>
                      </select>
                    ) : (
                      <input type="text" inputMode="decimal" autoComplete="off" spellCheck={false} value={String(config[key] ?? '')} onChange={(e) => handleChange(key, e.target.value)} />
                    )}
                    <em>{unit}</em>
                  </div>
                  <small>{note}</small>
                  {key === 'capillary_mode' && numericMode(config, 'capillary_mode') === 2 && (
                    <small className="input-warning">Mode ini menampilkan diameter kapiler saja. Panjang efektif dihitung otomatis oleh iterasi dari batas internal.</small>
                  )}
                  {key === 'capillary_mode' && numericMode(config, 'capillary_mode') === 3 && (
                    <small className="input-warning">Mode ini menampilkan panjang kapiler saja. Diameter efektif dihitung otomatis oleh iterasi dari batas internal.</small>
                  )}
                  {key === 'capillary_mode' && numericMode(config, 'capillary_mode') === 4 && (
                    <small className="input-warning">Mode auto-search memakai range internal untuk mencari kombinasi diameter dan panjang paling seimbang.</small>
                  )}
                </label>
              ))}
            </div>
            <div className="action-row sticky-actions">
              <button className="primary" onClick={runSimulation} disabled={loading || !groups.length}>{loading ? 'Menjalankan...' : 'Jalankan Simulasi'}</button>
              <button className="secondary" onClick={resetInput} disabled={loading}>Reset Input</button>
            </div>
          </aside>

          <section className="results-area">
            <div className="summary-grid summary-grid-extended">
              <SummaryCard label="Suhu Akhir Tangki" value={summary.finalTankMean_C} unit="°C" />
              <SummaryCard label="Waktu Set Point" value={summary.reachTime_min ?? '-'} unit="menit" />
              <SummaryCard label="COP AC + HWST" value={summary.COP_AC_integrated} unit="-" />
              <SummaryCard label="COP AC Konvensional" value={summary.COP_AC_conventional} unit="-" />
              <SummaryCard label="Peningkatan COP" value={summary.delta_COP_integrated_pct} unit="%" />
              <SummaryCard label="COP Useful Terintegrasi" value={summary.COP_useful_integrated} unit="-" />
            </div>
            <COPClassificationPanel summary={summary} />
            <div className="panel chart-panel">
              <div className="panel-title horizontal">
                <div><h2>Grafik Simulasi</h2><p>Kurva utama hasil simulasi terhadap waktu.</p></div>
                <div className="report-hint">Report Excel/PDF tersedia di navigasi atas.</div>
              </div>
              {results?.time_series?.length ? (
                <div className="charts charts-two-tier">
                  <LineChart data={results.time_series} xKey="time_min" yKey="T_tank_mean_C" title="Suhu Air Tangki vs Waktu" yLabel="°C" xAxisLabel="Waktu simulasi (menit)" yAxisLabel="Temperatur air tangki (°C)" />
                  <LineChart data={results.time_series} xKey="time_min" yKey="COP_AC" title="COP AC vs Waktu" yLabel="COP" xAxisLabel="Waktu simulasi (menit)" yAxisLabel="COP AC" />
                  <LineChart data={results.time_series} xKey="time_min" yKey="Q_HWST_kW" title="Q HWST vs Waktu" yLabel="kW" xAxisLabel="Waktu simulasi (menit)" yAxisLabel="Laju panas HWST (kW)" />
                  <RecommendedRangeChart data={results.time_series} summary={summary} config={results.config} />
                </div>
              ) : <div className="empty-state">Klik <strong>Jalankan Simulasi</strong> untuk menampilkan grafik.</div>}
            </div>
            <CoilUsagePanel results={results} />
            <DataTables results={results} />
          </section>
        </section>
      )}

      {page === 'visualisasi' && <SystemJourneyPage results={results} onRun={runSimulation} loading={loading} setPage={setPage} onDownload={downloadExport} />}
      {page === 'ph' && <PHDiagramPage results={results} onRun={runSimulation} loading={loading} />}
    </main>
  )
}


const COP_BANDS = [
  { grade: 'A', range: 'COP > 3.60', label: 'Sangat efisien' },
  { grade: 'B', range: '3.60 ≥ COP > 3.40', label: 'Efisien' },
  { grade: 'C', range: '3.40 ≥ COP > 3.20', label: 'Cukup efisien' },
  { grade: 'D', range: '3.20 ≥ COP > 2.80', label: 'Menengah' },
  { grade: 'E', range: '2.80 ≥ COP > 2.60', label: 'Kurang efisien' },
  { grade: 'F', range: '2.60 ≥ COP > 2.40', label: 'Rendah' },
  { grade: 'G', range: '2.40 ≥ COP', label: 'Sangat rendah' },
]

function localCOPClass(value: unknown) {
  const v = Number(value)
  if (!Number.isFinite(v)) return { grade: '-', range: '-', label: 'Belum tersedia' }
  if (v > 3.60) return COP_BANDS[0]
  if (v > 3.40) return COP_BANDS[1]
  if (v > 3.20) return COP_BANDS[2]
  if (v > 2.80) return COP_BANDS[3]
  if (v > 2.60) return COP_BANDS[4]
  if (v > 2.40) return COP_BANDS[5]
  return COP_BANDS[6]
}

function COPClassificationPanel({ summary }: { summary: Record<string, number | string | null> }) {
  const hasData = summary.COP_AC_integrated !== undefined || summary.COP_AC_conventional !== undefined || summary.COP_nameplate !== undefined
  if (!hasData) return null

  const integrated = localCOPClass(summary.COP_AC_integrated)
  const conventional = localCOPClass(summary.COP_AC_conventional)
  const nameplate = localCOPClass(summary.COP_nameplate)
  const active = String(summary.COP_class_integrated || integrated.grade)
  const rows = [
    { label: 'AC + HWST', value: summary.COP_AC_integrated, classInfo: { ...integrated, grade: String(summary.COP_class_integrated || integrated.grade), label: String(summary.COP_class_integrated_label || integrated.label), range: String(summary.COP_class_integrated_range || integrated.range) } },
    { label: 'AC konvensional', value: summary.COP_AC_conventional, classInfo: { ...conventional, grade: String(summary.COP_class_conventional || conventional.grade), label: String(summary.COP_class_conventional_label || conventional.label), range: String(summary.COP_class_conventional_range || conventional.range) } },
    { label: 'Nameplate', value: summary.COP_nameplate, classInfo: { ...nameplate, grade: String(summary.COP_class_nameplate || nameplate.grade), label: String(summary.COP_class_nameplate_label || nameplate.label), range: String(summary.COP_class_nameplate_range || nameplate.range) } },
  ]

  return <div className="panel cop-class-panel">
    <div className="panel-title horizontal">
      <div>
        <h2>Klasifikasi Efisiensi Berdasarkan COP</h2>
        <p>Skala A–G hanya untuk COP pendinginan AC. COP useful tidak diklasifikasikan karena memasukkan manfaat pemanasan air.</p>
      </div>
      <div className="cop-current-badge"><span>Kelas AC + HWST</span><strong>{active}</strong></div>
    </div>
    <div className="cop-class-layout">
      <div className="cop-ladder" aria-label="Skala kelas COP A sampai G">
        {COP_BANDS.map((band) => <div key={band.grade} className={`cop-band cop-grade-${band.grade} ${active === band.grade ? 'active' : ''}`}>
          <strong>{band.grade}</strong><span>{band.range}</span>
        </div>)}
      </div>
      <div className="cop-class-table">
        {rows.map((row) => <div key={row.label} className="cop-result-row">
          <span>{row.label}</span>
          <strong>{fmt(Number(row.value), 3)}</strong>
          <b className={`cop-pill cop-grade-${row.classInfo.grade}`}>{row.classInfo.grade}</b>
          <small>{row.classInfo.label} · {row.classInfo.range}</small>
        </div>)}
      </div>
    </div>
  </div>
}

function SummaryCard({ label, value, unit }: { label: string; value: unknown; unit: string }) {
  return <div className="summary-card"><span>{label}</span><strong>{value === undefined || value === null ? '-' : String(value)}</strong><small>{unit}</small></div>
}

function LineChart({ data, xKey, yKey, title, yLabel, xAxisLabel = 'Waktu simulasi (menit)', yAxisLabel = yLabel }: { data: TimeRow[]; xKey: string; yKey: string; title: string; yLabel: string; xAxisLabel?: string; yAxisLabel?: string }) {
  const width = 520, height = 250, padL = 58, padR = 22, padT = 30, padB = 54
  const values = data.map((item) => Number(item[yKey])).filter(Number.isFinite)
  const xValues = data.map((item) => Number(item[xKey])).filter(Number.isFinite)
  if (!values.length || !xValues.length) return <div className="chart-card">Tidak ada data</div>
  const rawMin = Math.min(...values), rawMax = Math.max(...values)
  let scaleMin = rawMin, scaleMax = rawMax
  // Untuk grafik COP, hindari zoom berlebihan agar selisih kecil tidak terlihat terlalu besar.
  if (title.toLowerCase().includes('cop') && (scaleMax - scaleMin) < 0.5) {
    const mid = (scaleMax + scaleMin) / 2
    scaleMin = mid - 0.25
    scaleMax = mid + 0.25
  }
  const yPad = Math.max((scaleMax - scaleMin) * 0.08, Math.abs(scaleMax) * 0.02, 0.05)
  const yMin = scaleMin - yPad, yMax = scaleMax + yPad
  const xMin = Math.min(...xValues), xMax = Math.max(...xValues)
  const sx = (x: number) => padL + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - padL - padR)
  const sy = (y: number) => height - padB - ((y - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - padT - padB)
  const points = data.map((item) => {
    const x = Number(item[xKey]), y = Number(item[yKey])
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null
    return `${sx(x)},${sy(y)}`
  }).filter(Boolean).join(' ')
  const xTicks = makeTimeTicks(xMin, xMax, 5)
  const yTicks = makeTicks(yMin, yMax, 5)
  return <div className="chart-card chart-card-v9">
    <div className="chart-header"><h3>{title}</h3><span>{yLabel}</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${title}, sumbu X ${xAxisLabel}, sumbu Y ${yAxisLabel}`}>
      {yTicks.map((tick) => <g key={`y-${tick}`}><line className="grid-line" x1={padL} y1={sy(tick)} x2={width-padR} y2={sy(tick)} /><text className="axis-tick" x={padL-8} y={sy(tick)+4} textAnchor="end">{fmt(tick, yLabel === 'COP' ? 2 : 1)}</text></g>)}
      {xTicks.map((tick) => <g key={`x-${tick}`}><line className="grid-line" x1={sx(tick)} y1={padT} x2={sx(tick)} y2={height-padB} /><text className="axis-tick" x={sx(tick)} y={height-padB+18} textAnchor="middle">{fmt(tick,0)}</text></g>)}
      <line className="axis-line" x1={padL} y1={height-padB} x2={width-padR} y2={height-padB}/>
      <line className="axis-line" x1={padL} y1={padT} x2={padL} y2={height-padB}/>
      <polyline className="chart-line-blue" points={points} />
      <text className="axis-label-y" x="14" y={height/2} transform={`rotate(-90 14 ${height/2})`} textAnchor="middle">{yAxisLabel}</text>
      <text className="axis-label-x" x={(padL+width-padR)/2} y={height-12} textAnchor="middle">{xAxisLabel}</text>
    </svg>
  </div>
}

function RecommendedRangeChart({ data, summary, config }: { data: TimeRow[]; summary: Record<string, number | string | null>; config: Config }) {
  const width = 520, height = 250, padL = 58, padR = 22, padT = 30, padB = 54
  const recMinRaw = Number(summary.COPMaxRangeMin_C)
  const recMaxRaw = Number(summary.COPMaxRangeMax_C)
  const hasRange = Number.isFinite(recMinRaw) && Number.isFinite(recMaxRaw) && recMaxRaw > recMinRaw
  const recMin = hasRange ? recMinRaw : 40
  const recMax = hasRange ? recMaxRaw : Math.max(50, Number(config.T_setpoint_C) || 50)
  const upperMax = Math.min(recMax + 5, 60)
  const xMin = 30, xMax = Math.max(60, recMax + 10)
  const yMin = 0, yMax = 105
  const sx = (x: number) => padL + ((x - xMin) / Math.max(xMax - xMin, 1e-9)) * (width - padL - padR)
  const sy = (y: number) => height - padB - ((y - yMin) / Math.max(yMax - yMin, 1e-9)) * (height - padT - padB)
  const raw = data.map(row => ({ t: num(row.T_tank_mean_C, NaN), q: num(row.Q_HWST_kW, NaN) })).filter(p => Number.isFinite(p.t) && Number.isFinite(p.q) && p.q > 0).sort((a,b) => a.t-b.t)
  const qMax = raw.reduce((m,p) => Math.max(m, p.q), 0) || 1
  const nearestActual = (temp: number) => {
    if (!raw.length) return null
    const nearest = raw.reduce((best, p) => Math.abs(p.t-temp) < Math.abs(best.t-temp) ? p : best, raw[0])
    if (Math.abs(nearest.t - temp) <= 2.75) return clamp((nearest.q / qMax) * 100, 0, 100)
    return null
  }
  const points = Array.from({length: Math.floor((xMax-xMin)/5)+1}, (_, i) => {
    const t = xMin + i*5
    const actual = nearestActual(t)
    const idx = actual ?? clamp(100 - 1.55*(t - 30) - 0.024*(t - 30)*(t - 30), 20, 100)
    return [t, idx] as [number, number]
  })
  const path = points.map(([t, idx]) => `${sx(t)},${sy(idx)}`).join(' ')
  const xTicks = points.map(([t]) => t)
  const yTicks = [0,25,50,75,100]
  const shade = (a: number, b: number, cls: string) => {
    const xa = Math.max(xMin, a), xb = Math.min(xMax, b)
    if (xb <= xa) return null
    return <rect className={cls} x={sx(xa)} y={padT} width={sx(xb)-sx(xa)} height={height-padT-padB} />
  }
  return <div className="chart-card chart-card-v9 range-chart-card">
    <div className="chart-header"><h3>Range Suhu COP Optimum Mode DSH</h3><span>{fmt(recMin,1)}–{fmt(recMax,1)} °C</span></div>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Range suhu COP optimum mode DSH dengan sumbu X suhu air dan sumbu Y indeks efektivitas heat recovery">
      {shade(recMin, recMax, 'range-shade-good')}
      {shade(recMax, upperMax, 'range-shade-limit')}
      {shade(upperMax, xMax, 'range-shade-bad')}
      {yTicks.map((tick) => <g key={`y-${tick}`}><line className="grid-line" x1={padL} y1={sy(tick)} x2={width-padR} y2={sy(tick)} /><text className="axis-tick" x={padL-8} y={sy(tick)+4} textAnchor="end">{tick}</text></g>)}
      {xTicks.map((tick) => <g key={`x-${tick}`}><line className="grid-line" x1={sx(tick)} y1={padT} x2={sx(tick)} y2={height-padB} /><text className="axis-tick" x={sx(tick)} y={height-padB+18} textAnchor="middle">{tick}</text></g>)}
      <line className="axis-line" x1={padL} y1={height-padB} x2={width-padR} y2={height-padB}/>
      <line className="axis-line" x1={padL} y1={padT} x2={padL} y2={height-padB}/>
      <polyline className="range-line" points={path} />
      {points.map(([t, idx]) => <circle key={t} className="range-dot" cx={sx(t)} cy={sy(idx)} r="3.8" />)}
      <text className="axis-label-y" x="14" y={height/2} transform={`rotate(-90 14 ${height/2})`} textAnchor="middle">Indeks efektivitas heat recovery (%)</text>
      <text className="axis-label-x" x={(padL+width-padR)/2} y={height-12} textAnchor="middle">Suhu air HWST (°C)</text>
    </svg>
    <div className="range-legend"><span><i className="legend-good" />Range COP optimum</span><span><i className="legend-limit" />Batas atas operasional</span><span><i className="legend-bad" />Kurang direkomendasikan</span></div>
  </div>
}


function useTimeline(length: number) {
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  useEffect(() => setIdx(0), [length])
  useEffect(() => {
    if (!playing || length < 2) return
    const timer = window.setInterval(() => setIdx((prev) => (prev >= length - 1 ? 0 : prev + 1)), Math.max(70, 420 / speed))
    return () => window.clearInterval(timer)
  }, [playing, speed, length])
  return { idx: Math.min(idx, Math.max(length - 1, 0)), setIdx, playing, setPlaying, speed, setSpeed }
}

function TimelineControl({ idx, setIdx, length, playing, setPlaying, speed, setSpeed, time }: { idx: number; setIdx: (n: number) => void; length: number; playing: boolean; setPlaying: (b: boolean) => void; speed: number; setSpeed: (n: number) => void; time: number }) {
  return <div className="timeline-control">
    <div><span>Waktu simulasi</span><strong>{fmt(time, 2)} min</strong></div>
    <input type="range" min={0} max={Math.max(length - 1, 0)} value={idx} onChange={(e) => setIdx(Number(e.target.value))} />
    <div className="timeline-buttons">
      <button className="secondary" onClick={() => setPlaying(!playing)}>{playing ? 'Pause' : 'Play'}</button>
      {[0.5, 1, 2, 5].map((s) => <button key={s} className={speed === s ? 'speed active-speed' : 'speed'} onClick={() => setSpeed(s)}>{s}×</button>)}
    </div>
  </div>
}


function SystemJourneyPage({ results, onRun, loading, setPage, onDownload }: { results: SimulationResults | null; onRun: () => void; loading: boolean; setPage: (p: Page) => void; onDownload: (type: 'excel' | 'pdf') => void }) {
  const series = results?.visualization_series?.length ? results.visualization_series : results?.time_series ?? []
  const { idx, setIdx, playing, setPlaying, speed, setSpeed } = useTimeline(series.length)
  const row = series[idx]
  if (!results || !series.length || !row) return <NeedRunPanel title="Visualisasi Perjalanan Sistem" onRun={onRun} loading={loading} />

  const totalMinutes = num(series[series.length - 1]?.time_min ?? 0)
  const currentTime = num(row.time_min)

  return (
    <section className="vis-reference-shell vis-no-sidebar">
      <div className="vis-reference-content">
        <header className="vis-page-header">
          <div className="vis-title-group">
            <h1>Visualisasi Simulasi Siklus Refrigeran AC + HWST</h1>
          </div>
          <div className="vis-header-actions">
            <div className="vis-update-card"><span className="dot" /> <strong>Update realtime</strong><small>Terhubung</small><button aria-label="Refresh">↻</button></div>
          </div>
        </header>

        <div className="vis-control-card">
          <div className="vis-controls-left">
            <button className="vis-ctrl-btn vis-ctrl-primary" onClick={() => setPlaying(!playing)}>
              <span>{playing ? '⏸' : '▶'}</span> {playing ? 'Pause' : 'Play'}
            </button>
            <button className="vis-ctrl-btn" onClick={() => { setPlaying(false); setIdx(0) }}>
              <span>■</span> Stop
            </button>
          </div>
          <div className="vis-time-block">
            <span>Waktu simulasi</span>
            <strong>{formatHMS(currentTime)}</strong>
            <em>/ {formatHMS(totalMinutes)}</em>
          </div>
          <input className="vis-slider" type="range" min={0} max={Math.max(series.length - 1, 0)} value={idx} onChange={(e) => setIdx(Number(e.target.value))} />
          <div className="vis-speed-block">
            <span>Kecepatan</span>
            <div className="vis-speed-list">
              {[0.5, 1, 2, 5].map((s) => (
                <button key={s} className={`vis-speed-btn${speed === s ? ' active' : ''}`} onClick={() => setSpeed(s)}>{s}x</button>
              ))}
            </div>
          </div>
        </div>

        <div className="vis-main-layout">
          <div className="vis-diagram-card">
            <div className="vis-diagram-title">Diagram Siklus Refrigeran</div>
            <SystemSvg row={row} />
            <div className="vis-temp-scale-bar">
              <span>Skala Temperatur (°C)</span>
              <div className="vis-scale-gradient" />
              <div className="vis-scale-labels">
                {[-10,0,10,20,30,40,50,60,70,90].map(v => <span key={v}>{v}</span>)}
              </div>
              <div className="vis-scale-note">Catatan: Warna pipa menunjukkan temperatur refrigeran aktual pada timestep simulasi.</div>
            </div>
          </div>

          <div className="vis-right-col">
            <RealtimePanel row={row} />
            <ZoneCoilPanel row={row} />
          </div>
        </div>

        <VisualTrendStrip series={series} activeIdx={idx} />
      </div>
    </section>
  )
}

function SystemSvg({ row }: { row: TimeRow }) {
  const tComp = num(row.T_comp_out_C), tHwst = num(row.T_ref_out_HWST_C), tCond = num(row.T_cond_out_C), tEvapIn = num(row.T_evap_in_C), tEvapOut = num(row.T_evap_out_C), tTank = num(row.T_tank_mean_C)
  const qHwst = num(row.Q_HWST_kW), wComp = num(row.W_comp_kW)
  const cComp = tempColor(tComp), cHwst = tempColor(tHwst), cCond = tempColor(tCond), cEvapIn = tempColor(tEvapIn), cEvapOut = tempColor(tEvapOut)
  const dp = pressureDrops(row)

  // Layout: viewBox 860x420
  // KOMPRESOR: x=60, y=210 (left middle)
  // HWST:      x=260, y=40  (top center-left, horizontal tank)
  // KONDENSOR: x=650, y=60  (top right)
  // EVAPORATOR:x=240, y=260 (bottom center)
  // KAPILER:   x=490, y=318 (bottom center-right)

  return <div className="sys-diagram-wrap"><svg viewBox="0 0 880 440" className="sys-diagram-svg">
    <defs>
      <filter id="sd" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#0f172a" floodOpacity="0.10" /></filter>
      <linearGradient id="steelH" x1="0" x2="1"><stop offset="0%" stopColor="#e2e8f0"/><stop offset="20%" stopColor="#fff"/><stop offset="50%" stopColor="#f8fafc"/><stop offset="80%" stopColor="#e2e8f0"/><stop offset="100%" stopColor="#cbd5e1"/></linearGradient>
      <linearGradient id="copperG" x1="0" x2="1"><stop offset="0%" stopColor="#92400e"/><stop offset="40%" stopColor="#fbbf24"/><stop offset="100%" stopColor="#b45309"/></linearGradient>
      <linearGradient id="compBodyG" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4b5563"/><stop offset="40%" stopColor="#374151"/><stop offset="100%" stopColor="#1f2937"/></linearGradient>
      <marker id="flowArrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 Z" fill="rgba(255,255,255,.92)" />
      </marker>
    </defs>

    {/* === PIPES === */}
    {/* 1→2: Evap out → Comp (arah suction menuju kompresor) */}
    <PipeNew d="M310 290 L310 340 L110 340 L110 295" color={cEvapOut} />
    {/* 2→HWST: Comp top → HWST left */}
    <PipeNew d="M110 208 L110 112 L262 112" color={cComp} />
    {/* HWST right → Condenser top-left */}
    <PipeNew d="M498 112 L650 112 L650 92" color={cHwst} />
    {/* Condenser bottom → Kapiler */}
    <PipeNew d="M650 248 L650 338 L600 338" color={cCond} />
    {/* Kapiler → Evaporator */}
    <PipeNew d="M490 338 L418 338 L418 296" color={cEvapIn} />

    {/* === STATE LABELS === */}
    <StateLabelNew label="2" desc="Keluar kompresor" temp={tComp} x={112} y={152} color={cComp} anchor="left" />
    <StateLabelNew label="2'" desc="Keluar HWST" temp={tHwst} x={570} y={88} color={cHwst} anchor="center" />
    <StateLabelNew label="3" desc="Keluar kondensor" temp={tCond} x={658} y={312} color={cCond} anchor="left" />
    <StateLabelNew label="4" desc="Masuk evaporator" temp={tEvapIn} x={438} y={374} color={cEvapIn} anchor="center" />
    <StateLabelNew label="1" desc="Keluar evaporator" temp={tEvapOut} x={300} y={374} color={cEvapOut} anchor="center" />

    {/* === COMPONENTS === */}
    <CompressorNew x={50} y={200} color={cComp} power={wComp} />
    <HwstTankNew x={260} y={60} color={cHwst} tankTemp={tTank} row={row} qHwst={qHwst} />
    <CondenserNew x={610} y={60} row={row} />
    <CapillaryNew x={488} y={308} row={row} />
    <EvaporatorNew x={248} y={258} row={row} />

    {/* === PRESSURE DROP TAGS === */}
    <PressureBadge x={340} y={190} label="DP HWST" value={dp.hwst} />
    <PressureBadge x={695} y={278} label="DP kond" value={dp.cond} />
    <PressureBadge x={250} y={225} label="DP evap" value={dp.evap} />
    <PressureBadge x={500} y={292} label="DP kapiler" value={dp.capRequired ?? dp.capAvailable} />

  </svg></div>
}

function PipeNew({ d, color }: { d: string; color: string }) {
  return <g>
    <path d={d} stroke="#d1d5db" strokeWidth="16" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <path d={d} stroke="#fff" strokeWidth="12" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity=".6" />
    <path d={d} stroke={color} strokeWidth="9" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <path d={d} stroke="rgba(255,255,255,.85)" strokeWidth="2.5" fill="none" strokeDasharray="4 16" strokeLinecap="round" className="flow-dash" markerEnd="url(#flowArrow)" />
  </g>
}

function StateLabelNew({ label, desc, temp, x, y, color, anchor }: { label: string; desc: string; temp: number; x: number; y: number; color: string; anchor: 'left'|'center'|'right' }) {
  const w = Math.max(112, Math.min(154, desc.length * 6.4 + 40))
  const bx = anchor === 'center' ? x - w / 2 : anchor === 'right' ? x - w : x
  const tx = bx + 12
  return <g className="state-card-svg">
    <line x1={x} y1={y + 32} x2={x} y2={y + 58} stroke="#cbd5e1" strokeWidth="1.2" />
    <rect x={bx} y={y} width={w} height="46" rx="8" fill="#ffffff" stroke="#dbe4ee" opacity=".98" />
    <text x={tx} y={y+18} className="state-card-title" style={{fill: color}}>{label}</text>
    <text x={tx+20} y={y+18} className="state-card-desc">{desc}</text>
    <text x={tx+20} y={y+36} className="state-card-temp" style={{fill: color}}>{fmt(temp,1)}°C</text>
  </g>
}

function CompressorNew({ x, y, color, power }: { x: number; y: number; color: string; power: number }) {
  // Realistic compressor silhouette - cylindrical body
  return <g transform={`translate(${x},${y})`} filter="url(#sd)">
    {/* Shadow ellipse */}
    <ellipse cx="60" cy="148" rx="52" ry="8" fill="#9ca3af" opacity=".3" />
    {/* Body */}
    <path d="M22 32 Q22 8 60 8 Q98 8 98 32 L98 110 Q98 138 60 138 Q22 138 22 110 Z" fill="url(#compBodyG)" stroke="#111827" strokeWidth="1.8" />
    {/* Top dome */}
    <ellipse cx="60" cy="32" rx="38" ry="14" fill="#4b5563" stroke="#374151" strokeWidth="1.5" />
    {/* Highlight stripes */}
    {[46,62,78,94].map(yv => <line key={yv} x1="28" y1={yv} x2="92" y2={yv} stroke="rgba(255,255,255,.08)" strokeWidth="1.5" />)}
    {/* Color glow center */}
    <circle cx="60" cy="80" r="22" fill={color} opacity=".15" />
    <circle cx="60" cy="80" r="14" fill={color} opacity=".25" />
    {/* Port connections */}
    <rect x="52" y="0" width="16" height="10" rx="4" fill="#374151" stroke="#1f2937" />
    <rect x="52" y="136" width="16" height="12" rx="4" fill="#374151" stroke="#1f2937" />
    {/* Labels */}
    <text x="60" y="85" textAnchor="middle" style={{fontSize:11, fontWeight:900, fill:'#fff', letterSpacing:'.04em'}}>COMP</text>
    <text x="60" y="157" textAnchor="middle" style={{fontSize:11, fontWeight:900, fill:'#0f172a'}}>KOMPRESOR</text>
    <text x="60" y="172" textAnchor="middle" style={{fontSize:10, fill:'#64748b'}}>W = {fmt(power,2)} kW</text>
  </g>
}

function HwstTankNew({ x, y, color, tankTemp, row, qHwst }: { x: number; y: number; color: string; tankTemp: number; row: TimeRow; qHwst: number }) {
  // Dibuat flat/rectangular agar mudah divisualisasikan konsisten di kode.
  return <g transform={`translate(${x},${y})`} filter="url(#sd)">
    <ellipse cx="118" cy="100" rx="108" ry="10" fill="#9ca3af" opacity=".20" />
    <rect x="20" y="18" width="196" height="74" rx="0" fill="#f8fafc" stroke="#1e293b" strokeWidth="2" />
    <rect x="32" y="28" width="172" height="52" rx="0" fill="#ffffff" stroke="#e2e8f0" strokeWidth="1" />
    <rect x="34" y="30" width="168" height="48" rx="0" fill={tempColor(tankTemp)} opacity=".08" />
    <HwstCoilNew x={52} y={32} color={color} row={row} />
    <line x1="54" y1="92" x2="54" y2="108" stroke="#64748b" strokeWidth="4.5" strokeLinecap="round" />
    <line x1="182" y1="92" x2="182" y2="108" stroke="#64748b" strokeWidth="4.5" strokeLinecap="round" />
    <rect x="48" y="104" width="18" height="4" rx="1" fill="#94a3b8" />
    <rect x="176" y="104" width="18" height="4" rx="1" fill="#94a3b8" />
    <circle cx="20" cy="55" r="5" fill={color} stroke="#fff" strokeWidth="1.5" />
    <circle cx="216" cy="55" r="5" fill={color} stroke="#fff" strokeWidth="1.5" />
    <text x="118" y="128" textAnchor="middle" style={{fontSize:12, fontWeight:900, fill:'#0f172a'}}>HWST</text>
    <text x="118" y="143" textAnchor="middle" style={{fontSize:10, fill:'#64748b'}}>T air {fmt(tankTemp,1)}°C  |  Q {fmt(qHwst,2)} kW</text>
  </g>
}

function HwstCoilNew({ x, y, color, row }: { x: number; y: number; color: string; row: TimeRow }) {
  const zones = zoneTriplet(row.hwst_f_dsh, row.hwst_f_tp, row.hwst_f_sc)
  const d = buildHwstCoilPath(7, 18, 29, 8, 50)
  return <g transform={`translate(${x},${y})`}>
    <SegmentedPath d={d} zones={zones} strokeWidth={4.2} fallbackColor={color} />
    <path d={d} fill="none" stroke="rgba(255,255,255,.76)" strokeWidth="1.4" strokeDasharray="3 9" strokeLinecap="round" pathLength={100} />
  </g>
}

function buildHwstCoilPath(loopCount: number, pitch: number, mid: number, top: number, bottom: number) {
  let d = `M0 ${mid}`
  for (let i = 0; i < loopCount; i += 1) {
    const a = i * pitch
    const b = a + pitch / 2
    const c = a + pitch
    d += ` C${a} ${top} ${b} ${top} ${b} ${mid} C${b} ${bottom} ${c} ${bottom} ${c} ${mid}`
  }
  return d
}

function CondenserNew({ x, y, row }: { x: number; y: number; row: TimeRow }) {
  const dsh = pct(row.cond_f_dsh), tp = pct(row.cond_f_tp), sc = pct(row.cond_f_sc)
  return <g transform={`translate(${x},${y})`}>
    <ellipse cx="70" cy="150" rx="66" ry="7" fill="#94a3b8" opacity=".16" />
    <rect x="4" y="4" width="132" height="128" rx="0" fill="#ffffff" stroke="#1e293b" strokeWidth="2" />
    <rect x="16" y="16" width="108" height="88" rx="0" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1" />
    <FinLines x={24} y={20} w={92} h={80} count={10} />
    <CleanCondenserCoil x={25} y={27} w={90} rows={4} gap={18} row={row} />
    <circle cx="4" cy="28" r="5" fill={tempColor(num(row.T_ref_out_HWST_C))} stroke="#fff" strokeWidth="1.5" />
    <circle cx="70" cy="132" r="5" fill={tempColor(num(row.T_cond_out_C))} stroke="#fff" strokeWidth="1.5" />
    <text x="70" y="151" textAnchor="middle" style={{fontSize:11, fontWeight:900, fill:'#0f172a'}}>KONDENSOR</text>
    <text x="70" y="165" textAnchor="middle" style={{fontSize:9, fill:'#64748b'}}>DSH {fmt(dsh,1)}% · TP {fmt(tp,1)}% · SC {fmt(sc,1)}%</text>
  </g>
}

function CleanCondenserCoil({ x, y, w, rows, gap, row }: { x: number; y: number; w: number; rows: number; gap: number; row: TimeRow }) {
  const zones = normalizeSegments(zoneTriplet(row.cond_f_dsh, row.cond_f_tp, row.cond_f_sc))
  const d = buildCleanSerpentinePath(w, rows, gap)
  return <g transform={`translate(${x},${y})`}>
    <path d={d} fill="none" stroke="#ecfccb" strokeWidth="7.4" strokeLinecap="round" strokeLinejoin="round" />
    <SegmentedPathOnly d={d} zones={zones} strokeWidth={4.4} fallbackColor="#84cc16" />
    <path d={d} fill="none" stroke="rgba(255,255,255,.70)" strokeWidth="1.2" strokeDasharray="3 9" strokeLinecap="round" pathLength={100} />
  </g>
}

function EvaporatorNew({ x, y, row }: { x: number; y: number; row: TimeRow }) {
  return <g transform={`translate(${x},${y})`}>
    <ellipse cx="82" cy="118" rx="78" ry="7" fill="#94a3b8" opacity=".14" />
    <rect x="0" y="4" width="164" height="96" rx="0" fill="#ffffff" stroke="#1e293b" strokeWidth="2" />
    <rect x="12" y="16" width="140" height="58" rx="0" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1" />
    <CleanEvaporatorCoil x={24} y={24} w={116} rows={4} gap={13} row={row} />
    <text x="82" y="92" textAnchor="middle" style={{fontSize:12, fontWeight:900, fill:'#0f172a'}}>EVAPORATOR</text>
  </g>
}

function CleanEvaporatorCoil({ x, y, w, rows, gap, row }: { x: number; y: number; w: number; rows: number; gap: number; row: TimeRow }) {
  const zones = normalizeSegments(zonePair(row.evap_f_tp, row.evap_f_sh))
  const d = buildCleanSerpentinePath(w, rows, gap)
  return <g transform={`translate(${x},${y})`}>
    <path d={d} fill="none" stroke="#dbeafe" strokeWidth="7.2" strokeLinecap="round" strokeLinejoin="round" />
    <SegmentedPathOnly d={d} zones={zones} strokeWidth={4.2} fallbackColor="#2563eb" />
    <path d={d} fill="none" stroke="rgba(255,255,255,.72)" strokeWidth="1.2" strokeDasharray="3 9" strokeLinecap="round" pathLength={100} />
  </g>
}

function buildCleanSerpentinePath(w: number, rows: number, gap: number) {
  const r = gap / 2
  let d = `M${r} 0 H${w - r}`
  for (let i = 1; i < rows; i += 1) {
    const y = i * gap
    if (i % 2 === 1) {
      d += ` A${r} ${r} 0 0 1 ${w - r} ${y} H${r}`
    } else {
      d += ` A${r} ${r} 0 0 0 ${r} ${y} H${w - r}`
    }
  }
  return d
}

function CapillaryNew({ x, y, row }: { x: number; y: number; row: TimeRow }) {
  const dp = pressureDrops(row)
  const status = capStatusLabel(row)
  return <g transform={`translate(${x},${y})`} filter="url(#sd)">
    <line x1="-12" y1="24" x2="4" y2="24" stroke="url(#copperG)" strokeWidth="7" strokeLinecap="round" />
    <path d="M2 24 C12 4 28 4 38 24 C48 44 64 44 74 24 C84 4 100 4 110 24" fill="none" stroke="url(#copperG)" strokeWidth="7" strokeLinecap="round" />
    <line x1="110" y1="24" x2="126" y2="24" stroke="url(#copperG)" strokeWidth="7" strokeLinecap="round" />
    <path d="M2 24 C12 4 28 4 38 24 C48 44 64 44 74 24 C84 4 100 4 110 24" fill="none" stroke="rgba(255,255,255,.65)" strokeWidth="2" strokeDasharray="3 10" />
    <circle cx="2" cy="24" r="4.5" fill="#b45309" stroke="#fff" strokeWidth="1.5" />
    <circle cx="110" cy="24" r="4.5" fill="#b45309" stroke="#fff" strokeWidth="1.5" />
    <rect x="18" y="40" width="78" height="32" rx="10" fill="#fffbeb" stroke="#fed7aa" strokeWidth="1" />
    <text x="57" y="53" textAnchor="middle" style={{fontSize:10.5, fontWeight:900, fill:'#92400e'}}>KAPILER</text>
    <text x="57" y="66" textAnchor="middle" style={{fontSize:8.8, fill: status === 'Normal' ? '#16a34a' : '#ea580c', fontWeight:800}}>{status}</text>
    {Number.isFinite(dp.capRequired ?? NaN) && <text x="57" y="82" textAnchor="middle" style={{fontSize:8.5, fill:'#64748b'}}>DP req {fmt(dp.capRequired,0)} kPa</text>}
  </g>
}

function Pipe({ d, color, label, x, y, hot = false }: { d: string; color: string; label: string; x: number; y: number; hot?: boolean }) {
  const width = Math.min(248, Math.max(150, label.length * 6.3))
  return <g className="pipe-layer pipe-v9">
    <path d={d} stroke="#cbd5e1" strokeWidth="18" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity=".70" />
    <path d={d} stroke="#ffffff" strokeWidth="14" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity=".68" />
    <path d={d} stroke={color} strokeWidth="10" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    <path d={d} className="flow-dash" stroke={hot ? 'rgba(255,255,255,.90)' : 'rgba(255,255,255,.78)'} strokeWidth="3" fill="none" strokeDasharray="3 19" strokeLinecap="round" />
    <rect x={x-8} y={y-20} width={width} height="30" rx="9" fill="white" stroke="#dbe4ee" opacity=".96" />
    <text x={x} y={y} className="state-label state-label-v9">{label}</text>
  </g>
}

function CompressorClean({ x, y, color, power }: { x: number; y: number; color: string; power: number }) {
  return <g transform={`translate(${x},${y})`} filter="url(#softShadowV9)">
    <ellipse cx="72" cy="140" rx="60" ry="12" fill="#cbd5e1" opacity=".52" />
    <path d="M32 44 Q32 18 72 18 Q112 18 112 44 L112 112 Q112 142 72 142 Q32 142 32 112 Z" fill="#ffffff" stroke="#1e293b" strokeWidth="2.3" />
    <ellipse cx="72" cy="44" rx="40" ry="18" fill="#f1f5f9" stroke="#64748b" />
    <path d="M43 61 Q72 46 101 61" fill="none" stroke={color} strokeWidth="7" opacity=".38" strokeLinecap="round" />
    {[74,90,106,122].map(yv => <line key={yv} x1="40" y1={yv} x2="104" y2={yv} stroke="#dbe4ee" strokeWidth="2" />)}
    <circle cx="72" cy="91" r="25" fill={color} opacity=".10" stroke={color} strokeWidth="1.2" />
    <text x="72" y="93" textAnchor="middle" className="comp-label">COMP</text>
    <text x="72" y="166" textAnchor="middle" className="component-caption">W = {fmt(power,2)} kW</text>
  </g>
}

function HwstTankHorizontal({ x, y, color, tankTemp, row, qHwst }: { x: number; y: number; color: string; tankTemp: number; row: TimeRow; qHwst: number }) {
  return <g transform={`translate(${x},${y})`} filter="url(#softShadowV9)">
    <ellipse cx="128" cy="137" rx="132" ry="13" fill="#cbd5e1" opacity=".45" />
    <rect x="20" y="28" width="216" height="92" rx="46" fill="url(#tankSteelV9)" stroke="#1e293b" strokeWidth="2.2" />
    <ellipse cx="38" cy="74" rx="18" ry="43" fill="#f8fafc" stroke="#94a3b8" />
    <ellipse cx="218" cy="74" rx="18" ry="43" fill="#e2e8f0" stroke="#94a3b8" />
    <rect x="48" y="42" width="152" height="64" rx="22" fill={tempColor(tankTemp)} opacity=".10" />
    <HwstCoil x={56} y={48} color={color} row={row} />
    <line x1="58" y1="120" x2="58" y2="140" stroke="#64748b" strokeWidth="5" strokeLinecap="round" />
    <line x1="198" y1="120" x2="198" y2="140" stroke="#64748b" strokeWidth="5" strokeLinecap="round" />
    <circle cx="18" cy="74" r="5.8" fill={color} /><circle cx="238" cy="74" r="5.8" fill={color} />
    <text x="128" y="161" textAnchor="middle" className="comp-label">HWST</text>
    <text x="128" y="181" textAnchor="middle" className="small-svg">T air {fmt(tankTemp,1)}°C  |  Q {fmt(qHwst,2)} kW</text>
  </g>
}

function HwstCoil({ x, y, color, row }: { x: number; y: number; color: string; row: TimeRow }) {
  const dsh = pct(row.hwst_f_dsh), tp = pct(row.hwst_f_tp), sc = pct(row.hwst_f_sc)
  const colors = ['#dc2626', '#f59e0b', '#22c55e']
  return <g transform={`translate(${x},${y})`}>
    {[0,1,2,3,4,5,6].map((i) => {
      const zoneColor = i < Math.round(dsh/100*7) ? colors[0] : i < Math.round((dsh+tp)/100*7) ? colors[1] : colors[2]
      const cx = i * 20
      return <path key={i} d={`M${cx} 4 C${cx} 18 ${cx+16} 18 ${cx+16} 32 C${cx+16} 48 ${cx} 48 ${cx} 60`} fill="none" stroke={zoneColor || color} strokeWidth="4" strokeLinecap="round" />
    })}
  </g>
}

function CondenserClean({ x, y, row }: { x: number; y: number; row: TimeRow }) {
  const dsh = pct(row.cond_f_dsh), tp = pct(row.cond_f_tp), sc = pct(row.cond_f_sc)
  return <g transform={`translate(${x},${y})`} filter="url(#softShadowV9)">
    <ellipse cx="78" cy="176" rx="78" ry="10" fill="#cbd5e1" opacity=".42" />
    <rect x="0" y="0" width="156" height="164" rx="20" fill="#ffffff" stroke="#1e293b" strokeWidth="2.2" />
    <rect x="14" y="18" width="128" height="112" rx="12" fill="#f8fafc" stroke="#cbd5e1" />
    <FinLines x={24} y={22} w={108} h={104} count={9} />
    <CondenserSerpentine x={22} y={28} w={112} row={row} />
    <circle cx="0" cy="30" r="6" fill={tempColor(num(row.T_ref_out_HWST_C))} stroke="#fff" strokeWidth="2" />
    <circle cx="78" cy="164" r="6" fill={tempColor(num(row.T_cond_out_C))} stroke="#fff" strokeWidth="2" />
    <circle cx="78" cy="82" r="30" fill="none" stroke="#dbe4ee" strokeDasharray="6 6" />
    <circle cx="78" cy="82" r="7" fill="#e2e8f0" stroke="#64748b" />
    <text x="78" y="148" textAnchor="middle" className="comp-label">KONDENSOR</text>
    <text x="78" y="181" textAnchor="middle" className="small-svg">DSH {fmt(dsh,1)}% · TP {fmt(tp,1)}% · SC {fmt(sc,1)}%</text>
  </g>
}

function CondenserSerpentine({ x, y, w, row }: { x: number; y: number; w: number; row: TimeRow }) {
  const zones = zoneTriplet(row.cond_f_dsh, row.cond_f_tp, row.cond_f_sc)
  const d = buildSerpentinePath(w, 6, 16, false)
  return <g transform={`translate(${x},${y})`}>
    <SegmentedPath d={d} zones={zones} strokeWidth={4.8} fallbackColor="#f59e0b" />
    <path d={d} fill="none" stroke="rgba(255,255,255,.72)" strokeWidth="1.5" strokeDasharray="3 10" strokeLinecap="round" pathLength={100} />
  </g>
}

function buildSerpentinePath(w: number, rows: number, gap: number, reverseStart = false) {
  const r = gap / 2
  let d = `M${reverseStart ? w - r : r} 0 H${reverseStart ? r : w - r}`
  for (let i = 1; i < rows; i += 1) {
    const y = i * gap
    const atRight = reverseStart ? i % 2 === 0 : i % 2 === 1
    if (atRight) {
      d += ` A${r} ${r} 0 0 1 ${w - r} ${y} H${r}`
    } else {
      d += ` A${r} ${r} 0 0 0 ${r} ${y} H${w - r}`
    }
  }
  return d
}

function EvaporatorClean({ x, y, row }: { x: number; y: number; row: TimeRow }) {
  return <g transform={`translate(${x},${y})`} filter="url(#softShadowV9)">
    <rect x="0" y="0" width="168" height="112" rx="20" fill="#ffffff" stroke="#1e293b" strokeWidth="2.2" />
    <FinLines x={18} y={15} w={132} h={72} count={10} />
    <CoilHorizontal x={24} y={25} w={120} rows={5} row={row} type="evap" />
    <text x="84" y="101" textAnchor="middle" className="comp-label">EVAPORATOR</text>
  </g>
}

function CoilHorizontal({ x, y, w, rows, row, type }: { x: number; y: number; w: number; rows: number; color?: string; row: TimeRow; type: 'hwst'|'cond'|'evap' }) {
  const zones = type === 'evap'
    ? zonePair(row.evap_f_tp, row.evap_f_sh)
    : zoneTriplet(row.hwst_f_dsh, row.hwst_f_tp, row.hwst_f_sc)
  const d = buildSerpentinePath(w, rows, 13, type === 'evap')
  return <g transform={`translate(${x},${y})`}>
    <SegmentedPath d={d} zones={zones} strokeWidth={4.7} fallbackColor="#2563eb" />
    <path d={d} fill="none" stroke="rgba(255,255,255,.72)" strokeWidth="1.5" strokeDasharray="3 9" strokeLinecap="round" pathLength={100} />
  </g>
}

function CoilVertical({ x, y, h, cols, row, type }: { x: number; y: number; h: number; cols: number; row: TimeRow; type: 'cond' }) {
  const tp = pct(row.cond_f_tp), sc = pct(row.cond_f_sc)
  return <g transform={`translate(${x},${y})`}>{Array.from({length: cols}).map((_, i) => <line key={i} x1={i*15} y1="0" x2={i*15} y2={h} stroke={i < cols*(tp/100) ? '#f59e0b' : '#22c55e'} strokeWidth="4" strokeLinecap="round" />)}</g>
}

function FinLines({ x, y, w, h, count }: { x: number; y: number; w: number; h: number; count: number }) {
  return <g>{Array.from({ length: count }).map((_, i) => <line key={i} x1={x + i*w/(count-1)} y1={y} x2={x + i*w/(count-1)} y2={y+h} stroke="#cbd5e1" strokeWidth="1.1" />)}</g>
}

function CapillaryClean({ x, y }: { x: number; y: number }) {
  return <g transform={`translate(${x},${y})`} filter="url(#softShadowV9)">
    <line x1="-14" y1="28" x2="2" y2="28" stroke="url(#capCopper)" strokeWidth="8" strokeLinecap="round" />
    <path d="M0 28 C10 6 26 6 36 28 C46 50 62 50 72 28 C82 6 98 6 108 28" fill="none" stroke="url(#capCopper)" strokeWidth="8" strokeLinecap="round" />
    <line x1="108" y1="28" x2="124" y2="28" stroke="url(#capCopper)" strokeWidth="8" strokeLinecap="round" />
    <path d="M0 28 C10 6 26 6 36 28 C46 50 62 50 72 28 C82 6 98 6 108 28" fill="none" stroke="rgba(255,255,255,.70)" strokeWidth="2.5" strokeDasharray="3 11" strokeLinecap="round" />
    <circle cx="0" cy="28" r="5" fill="#b45309" stroke="#fff" strokeWidth="2" />
    <circle cx="108" cy="28" r="5" fill="#b45309" stroke="#fff" strokeWidth="2" />
    <rect x="28" y="45" width="52" height="21" rx="10" fill="#fff7ed" stroke="#fed7aa" />
    <text x="54" y="60" textAnchor="middle" className="comp-label">KAPILER</text>
  </g>
}

function TemperatureLegend() {
  return <g><text x="0" y="0" className="component-caption">Skala temperatur (°C)</text><rect x="0" y="13" width="330" height="12" rx="6" fill="url(#tempScaleV9)" /><text x="0" y="43" className="small-svg">rendah</text><text x="292" y="43" className="small-svg">tinggi</text></g>
}

function RealtimePanel({ row }: { row: TimeRow }) {
  const drop = pressureDrops(row)
  const items: Array<[string, string, string, string, string?]> = [
    ['time', 'Waktu simulasi', formatHMS(num(row.time_min)), '', 'clock'],
    ['tank', 'T air tangki', fmt(num(row.T_tank_mean_C),1), '°C', 'thermo'],
    ['cop', 'COP AC', fmt(num(row.COP_AC),2), '', 'cop'],
    ['useful', 'COP useful', fmt(num(row.COP_useful),2), '', 'useful'],
    ['hwst', 'Q HWST', fmt(num(row.Q_HWST_kW),2), 'kW', 'drop'],
    ['power', 'Daya kompresor', fmt(num(row.W_comp_kW),2), 'kW', 'bolt'],
    ['dp', 'Pressure drop total', fmt(drop.total,1), 'kPa', 'gauge'],
    ['cap', 'Status kapiler', capStatusLabel(row), '', 'check'],
  ]
  return <div className="rt-panel">
    <div className="rt-header"><h3>Metrik Realtime</h3></div>
    <div className="rt-grid">
      {items.map(([key, label, val, unit, icon]) => (
        <div className={`rt-card${key === 'cap' ? ' status-card' : ''}`} key={label}>
          <div className={`rt-card-icon icon-${icon}`}>{iconGlyph(icon)}</div>
          <div className="rt-card-body">
            <span className="rt-card-label">{label}</span>
            <strong className="rt-card-val">{val} <em>{unit}</em></strong>
          </div>
        </div>
      ))}
    </div>
    <PressureBreakdown drop={drop} />
  </div>
}

function PressureBreakdown({ drop }: { drop: PressureDropInfo }) {
  return <div className="dp-breakdown">
    <div><span>HWST</span><strong>{fmt(drop.hwst,1)}</strong></div>
    <div><span>Kond</span><strong>{fmt(drop.cond,1)}</strong></div>
    <div><span>Evap</span><strong>{fmt(drop.evap,1)}</strong></div>
    <div><span>High/Low</span><strong>{fmt(drop.high,1)} / {fmt(drop.low,1)}</strong></div>
  </div>
}

function iconGlyph(icon?: string) {
  const map: Record<string, string> = { clock: '◷', thermo: '♨', cop: '♙', useful: '♧', drop: '♨', bolt: 'ϟ', gauge: '◜', check: '✓' }
  return map[icon ?? ''] ?? '•'
}

function ZoneCoilPanel({ row }: { row: TimeRow }) {
  const hwst = [['DSH', pct(row.hwst_f_dsh)], ['TP', pct(row.hwst_f_tp)], ['SC', pct(row.hwst_f_sc)]] as Array<[string, number]>
  const cond = [['DSH', pct(row.cond_f_dsh)], ['TP', pct(row.cond_f_tp)], ['SC', pct(row.cond_f_sc)]] as Array<[string, number]>
  const evap = [['TP', pct(row.evap_f_tp)], ['SH', pct(row.evap_f_sh)]] as Array<[string, number]>
  const condDetail = `Subcool out: ${fmt(row.subcool_cond_C, 2)} K`
  const evapDetail = `Superheat out: ${fmt(row.superheat_evap_C, 2)} K`
  return <div className="rt-panel zone-coil-panel">
    <div className="rt-header"><h3>Zona Coil (%)</h3></div>
    <div className="zone-donut-row">
      <ZoneDonut title="HWST" zones={hwst} detail="Mode DSH" />
      <ZoneDonut title="Kondensor" zones={cond} detail={condDetail} />
      <ZoneDonut title="Evaporator" zones={evap} detail={evapDetail} />
    </div>
  </div>
}

function MetricGrid({ items }: { items: Array<[string, string, string]> }) { return <div className="metric-grid metric-grid-v9">{items.map(([label, value, unit]) => <div className="mini-card mini-card-v9" key={label}><span>{label}</span><strong>{value}</strong><em>{unit}</em></div>)}</div> }

function ZoneDonut({ title, zones, detail }: { title: string; zones: Array<[string, number]>; detail?: string }) {
  const segs = normalizeSegments(zones.map(([z, v]) => ({ key: z, label: z, value: v, color: zoneColor(z) })))
  let offset = 0
  return <div className="zone-donut-card zone-donut-card-v9">
    <strong className="zone-donut-title">{title}</strong>
    <div className="zone-donut-visual">
      <svg className="mini-donut-svg" viewBox="0 0 110 110" role="img" aria-label={`${title} zona coil`}>
        <circle cx="55" cy="55" r="38" fill="none" stroke="#e2e8f0" strokeWidth="20" />
        <g transform="rotate(-90 55 55)">
          {segs.map((seg) => {
            const current = offset
            offset += seg.pct ?? 0
            return <circle key={seg.key} cx="55" cy="55" r="38" fill="none" stroke={seg.color} strokeWidth="20" pathLength={100} strokeDasharray={`${Math.max(seg.pct ?? 0, 0.001)} ${Math.max(0, 100 - (seg.pct ?? 0))}`} strokeDashoffset={-current} />
          })}
        </g>
        <circle cx="55" cy="55" r="25" fill="#fff" stroke="#e2e8f0" />
      </svg>
    </div>
    <div className="mini-donut-legend mini-donut-legend-v9">
      {zones.map(([z,v]) => <span key={z}><i style={{background: zoneColor(z)}} />{z}<b>{fmt(pct(v),0)}%</b></span>)}
    </div>
    {detail && <div className="zone-donut-detail">{detail}</div>}
  </div>
}

function VisualTrendStrip({ series, activeIdx }: { series: TimeRow[]; activeIdx: number }) {
  const [range, setRange] = useState<'30min'|'1jam'|'2jam'>('2jam')
  if (!series.length) return null
  const rangeMinutes = range === '30min' ? 30 : range === '1jam' ? 60 : Number.POSITIVE_INFINITY
  const currentTime = num(series[Math.min(Math.max(activeIdx, 0), series.length - 1)]?.time_min ?? series[series.length - 1]?.time_min)
  const filtered = Number.isFinite(rangeMinutes) ? series.filter((row) => num(row.time_min) >= Math.max(0, currentTime - rangeMinutes) && num(row.time_min) <= currentTime) : series
  const activeTime = num(series[Math.min(Math.max(activeIdx,0), series.length-1)]?.time_min)
  const aIdx = Math.max(0, filtered.findIndex((row) => num(row.time_min) >= activeTime))

  return <div className="trend-strip">
    <div className="trend-strip-header">
      <strong>Tren Simulasi</strong>
      <label className="trend-range-select"><span>Rentang waktu</span>
        <select value={range} onChange={(e) => setRange(e.target.value as '30min'|'1jam'|'2jam')}>
          <option value="30min">30 Menit</option>
          <option value="1jam">1 Jam</option>
          <option value="2jam">2 Jam</option>
        </select>
      </label>
    </div>
    <div className="trend-charts-grid">
      <MultiLineMiniChart title="Temperatur Titik (°C)" data={filtered} keys={['T_evap_out_C','T_comp_out_C','T_ref_out_HWST_C','T_cond_out_C','T_evap_in_C']} labels={['Titik 1','Titik 2',"Titik 2'",'Titik 3','Titik 4']} activeIdx={aIdx} yAxisLabel="Temperatur (°C)" />
      <LineChartActive data={filtered} xKey="time_min" yKey="T_tank_mean_C" title="Suhu Air Tangki (°C)" yLabel="°C" activeIdx={aIdx} yAxisLabel="Suhu Air (°C)" />
      <MultiLineMiniChart title="COP" data={filtered} keys={['COP_AC','COP_useful']} labels={['COP AC','COP useful']} activeIdx={aIdx} yAxisLabel="COP" />
      <MultiLineMiniChart title="Zona Coil (%)" data={filtered} keys={['hwst_f_tp','cond_f_tp','evap_f_tp']} labels={['HWST TP','Kondensor TP','Evaporator TP']} activeIdx={aIdx} percent yAxisLabel="Persentase (%)" />
    </div>
  </div>
}

function LineChartActive({ data, xKey, yKey, title, yLabel, activeIdx, yAxisLabel }: { data: TimeRow[]; xKey: string; yKey: string; title: string; yLabel: string; activeIdx: number; yAxisLabel: string }) {
  const values = data.map((row) => num(row[yKey])).filter(Number.isFinite)
  if (!values.length) return <div className="chart-card">Tidak ada data</div>
  const w = 520, h = 230, padL = 54, padR = 20, padT = 28, padB = 46
  const minTime = Math.min(...data.map((r) => num(r[xKey])).filter(Number.isFinite))
  const maxTime = Math.max(...data.map((r) => num(r[xKey])).filter(Number.isFinite))
  const rawMin = Math.min(...values), rawMax = Math.max(...values)
  const yMin = Math.min(0, Math.floor(rawMin / 10) * 10)
  const yMax = Math.max(50, Math.ceil(rawMax / 10) * 10)
  const spanY = Math.max(yMax - yMin, 1e-6)
  const spanX = Math.max(maxTime - minTime, 1e-6)
  const xScale = (t: number) => padL + ((t - minTime) / spanX) * (w - padL - padR)
  const yScale = (v: number) => h - padB - ((v - yMin) / spanY) * (h - padT - padB)
  const pts = data.map((row) => [xScale(num(row[xKey])), yScale(num(row[yKey]))])
  const p = pts.map(([x, y]) => `${x},${y}`).join(' ')
  const active = pts[Math.min(Math.max(activeIdx, 0), pts.length - 1)] ?? [padL, h-padB]
  const activeRow = data[Math.min(Math.max(activeIdx, 0), data.length - 1)] ?? {}
  const xTicks = makeTimeTicks(minTime, maxTime, 5)
  const yTicks = makeTicks(yMin, yMax, 5)
  return <div className="chart-card chart-card-v9">
    <div className="chart-header"><h3>{title}</h3><span>{fmt(activeRow[yKey],2)} {yLabel}</span></div>
    <svg viewBox={`0 0 ${w} ${h}`}>
      {yTicks.map((tick) => <g key={`y-${tick}`}><line className="grid-line" x1={padL} y1={yScale(tick)} x2={w-padR} y2={yScale(tick)} /><text className="axis-tick" x={padL-8} y={yScale(tick)+4} textAnchor="end">{fmt(tick,0)}</text></g>)}
      {xTicks.map((tick) => <g key={`x-${tick}`}><line className="grid-line" x1={xScale(tick)} y1={padT} x2={xScale(tick)} y2={h-padB} /><text className="axis-tick" x={xScale(tick)} y={h-padB+18} textAnchor="middle">{formatTimeTick(tick)}</text></g>)}
      <line className="axis-line" x1={padL} y1={h-padB} x2={w-padR} y2={h-padB}/><line className="axis-line" x1={padL} y1={padT} x2={padL} y2={h-padB}/>
      <polyline className="chart-line-blue" points={p}/>
      <line className="active-time-line" x1={active[0]} y1={padT} x2={active[0]} y2={h-padB} />
      <circle cx={active[0]} cy={active[1]} r="5" className="active-dot"/>
      <text className="axis-label-y" x="14" y={h/2} transform={`rotate(-90 14 ${h/2})`} textAnchor="middle">{yAxisLabel}</text>
      <text className="axis-label-x" x={(padL+w-padR)/2} y={h-8} textAnchor="middle">Waktu simulasi (jam:menit)</text>
    </svg>
    <div className="mini-legend"><span><i style={{background:'#2563eb'}} />T air tangki</span></div>
  </div>
}

function MultiLineMiniChart({ data, keys, labels, title, activeIdx, percent = false, yAxisLabel }: { data: TimeRow[]; keys: string[]; labels: string[]; title: string; activeIdx: number; percent?: boolean; yAxisLabel: string }) {
  const w = 520, h = 230, padL = 54, padR = 20, padT = 28, padB = 46
  const rawValues = data.flatMap(row => keys.map(k => percent ? pct(row[k]) : num(row[k]))).filter(Number.isFinite)
  if (!rawValues.length) return <div className="chart-card">Tidak ada data</div>
  const minTime = Math.min(...data.map((r) => num(r.time_min)).filter(Number.isFinite))
  const maxTime = Math.max(...data.map((r) => num(r.time_min)).filter(Number.isFinite))
  const rawMin = Math.min(...rawValues), rawMax = Math.max(...rawValues)
  const yMin = percent ? 0 : title === 'COP' ? 0 : Math.floor(Math.min(0, rawMin) / 20) * 20
  const yMax = percent ? 100 : title === 'COP' ? Math.max(6, Math.ceil(rawMax)) : Math.max(100, Math.ceil(rawMax / 20) * 20)
  const spanY = Math.max(yMax-yMin, 1e-6)
  const spanX = Math.max(maxTime-minTime, 1e-6)
  const xScale = (t: number) => padL + ((t - minTime) / spanX) * (w - padL - padR)
  const yScale = (v: number) => h - padB - ((v-yMin)/spanY) * (h-padT-padB)
  const colors = ['#2563eb','#dc2626','#f59e0b','#22c55e','#06b6d4','#9333ea']
  const poly = (k: string) => data.map((row) => `${xScale(num(row.time_min))},${yScale(percent ? pct(row[k]) : num(row[k]))}`).join(' ')
  const activeRow = data[Math.min(Math.max(activeIdx,0), data.length-1)] ?? {}
  const activeX = xScale(num(activeRow.time_min, minTime))
  const xTicks = makeTimeTicks(minTime, maxTime, 5)
  const yTicks = makeTicks(yMin, yMax, 5)
  return <div className="chart-card chart-card-v9 multi-chart">
    <div className="chart-header"><h3>{title}</h3><span>t={fmt(activeRow.time_min,1)} min</span></div>
    <svg viewBox={`0 0 ${w} ${h}`}>
      {yTicks.map((tick) => <g key={`y-${tick}`}><line className="grid-line" x1={padL} y1={yScale(tick)} x2={w-padR} y2={yScale(tick)} /><text className="axis-tick" x={padL-8} y={yScale(tick)+4} textAnchor="end">{fmt(tick,0)}{percent && tick === 100 ? '' : ''}</text></g>)}
      {xTicks.map((tick) => <g key={`x-${tick}`}><line className="grid-line" x1={xScale(tick)} y1={padT} x2={xScale(tick)} y2={h-padB} /><text className="axis-tick" x={xScale(tick)} y={h-padB+18} textAnchor="middle">{formatTimeTick(tick)}</text></g>)}
      <line className="axis-line" x1={padL} y1={h-padB} x2={w-padR} y2={h-padB}/><line className="axis-line" x1={padL} y1={padT} x2={padL} y2={h-padB}/>
      {keys.map((k,i) => <polyline key={k} points={poly(k)} style={{stroke: colors[i], fill:'none', strokeWidth:2.8, strokeDasharray: percent ? '7 5' : '0'}} />)}
      <line className="active-time-line" x1={activeX} y1={padT} x2={activeX} y2={h-padB} />
      {keys.map((k,i) => { const v = percent ? pct(activeRow[k]) : num(activeRow[k]); return <circle key={k+'dot'} cx={activeX} cy={yScale(v)} r="4.2" fill={colors[i]} stroke="white" strokeWidth="2"/> })}
      <text className="axis-label-y" x="14" y={h/2} transform={`rotate(-90 14 ${h/2})`} textAnchor="middle">{yAxisLabel}</text>
      <text className="axis-label-x" x={(padL+w-padR)/2} y={h-8} textAnchor="middle">Waktu simulasi (jam:menit)</text>
    </svg>
    <div className="mini-legend">{labels.map((l,i) => <span key={l}><i style={{background:colors[i]}} />{l}</span>)}</div>
  </div>
}

function makeTicks(min: number, max: number, count: number) {
  if (count <= 1) return [min]
  return Array.from({ length: count }, (_, i) => min + (max - min) * i / (count - 1))
}
function makeTimeTicks(min: number, max: number, count: number) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return [0]
  return Array.from({ length: count }, (_, i) => min + (max - min) * i / (count - 1))
}
function formatTimeTick(minutes: number) {
  const total = Math.max(0, Math.round(minutes))
  const h = Math.floor(total / 60)
  const m = total % 60
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`
}

function capStatusLabel(row: TimeRow) {
  const code = num(row.capillary_status_code ?? row.capillaryStatusCode ?? 0)
  if (code === 5) return 'Normal'
  if (code === 2) return 'Underfeed'
  if (code === 3) return 'Overfeed'
  return String(row.capillary_status ?? row.capillaryStatus ?? 'Normal')
}

function PHDiagramPage({ results, onRun, loading }: { results: SimulationResults | null; onRun: () => void; loading: boolean }) {
  const frames = results?.ph_series ?? []
  const conventional = results?.ph_conventional
  const { idx, setIdx, playing, setPlaying, speed, setSpeed } = useTimeline(frames.length)
  const frame = frames[idx]
  if (!results || !frames.length || !frame) return <NeedRunPanel title="Diagram P-h Bergerak" onRun={onRun} loading={loading} />
  return <section className="single-page"><div className="panel visual-panel"><div className="panel-title horizontal"><div><h2>Diagram P-h Pembanding</h2><p>Diagram menampilkan 2 kondisi sekaligus: siklus AC + HWST (bergerak mengikuti timestep) dan siklus AC konvensional (pembanding tetap). Titik 2' hanya ada pada sistem HWST.</p></div><Badge>{results.ph_dome?.source ?? 'CoolProp'}</Badge></div><div className="ph-layout"><PHChart frame={frame} baseline={conventional} dome={results.ph_dome} /><PHStateTable frame={frame} baseline={conventional} /></div><TimelineControl idx={idx} setIdx={setIdx} length={frames.length} playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} time={Number(frame.time_min)} /></div></section>
}

function PHChart({ frame, baseline, dome }: { frame: PhFrame; baseline?: PhFrame; dome?: PhDome }) {
  const w = 900, h = 540, padL = 78, padR = 36, padT = 46, padB = 64
  const domeClosed = (dome?.liquid?.length && dome?.vapor?.length) ? [...dome.liquid, ...[...dome.vapor].reverse()] : []
  const all = [...(dome?.liquid ?? []), ...(dome?.vapor ?? []), ...frame.points, ...(baseline?.points ?? [])].filter((p) => Number.isFinite(Number(p.h_kJ_kg)) && Number.isFinite(Number(p.P_kPa)) && Number(p.P_kPa) > 0)
  const hMin = Math.min(...all.map(p => Number(p.h_kJ_kg))) - 25, hMax = Math.max(...all.map(p => Number(p.h_kJ_kg))) + 35
  const pMin = Math.max(100, Math.min(...all.map(p => Number(p.P_kPa))) * 0.70), pMax = Math.max(...all.map(p => Number(p.P_kPa))) * 1.35
  const logMin = Math.log10(pMin), logMax = Math.log10(pMax)
  const sx = (hv: number) => padL + ((hv - hMin) / Math.max(hMax - hMin, 1e-9)) * (w - padL - padR)
  const sy = (pv: number) => h - padB - ((Math.log10(Math.max(pv, 1)) - logMin) / Math.max(logMax - logMin, 1e-9)) * (h - padT - padB)
  const pth = (pts: Array<{h_kJ_kg:number;P_kPa:number}>) => pts.map(p => `${sx(p.h_kJ_kg)},${sy(p.P_kPa)}`).join(' ')
  const cycle = [...frame.points, frame.points[0]]
  const baseCycle = baseline?.points?.length ? [...baseline.points, baseline.points[0]] : []
  const colors: Record<string, string> = { '1':'#0891b2', '2':'#dc2626', "2'":'#ea580c', '3':'#2563eb', '4':'#f59e0b' }
  const offsets: Record<string, [number, number]> = { '1':[-86, 34], '2':[12, -36], "2'":[-110, -34], '3':[-4, -34], '4':[-82, 26] }
  return <div className="ph-chart-wrap"><svg viewBox={`0 0 ${w} ${h}`} className="ph-svg">
    <rect x="16" y="16" width={w-32} height={h-32} rx="24" fill="#fff" stroke="#e2e8f0" />
    {[0,1,2,3,4].map(i => { const y = padT + i*(h-padT-padB)/4; const pVal = Math.pow(10, logMax - i*(logMax-logMin)/4); return <g key={i}><line x1={padL} y1={y} x2={w-padR} y2={y} stroke="#e2e8f0"/><text x="24" y={y+4} className="axis-text">{fmt(pVal,0)}</text></g> })}
    {[0,1,2,3,4].map(i => { const x = padL + i*(w-padL-padR)/4; const hVal = hMin + i*(hMax-hMin)/4; return <g key={`x${i}`}><line x1={x} y1={padT} x2={x} y2={h-padB} stroke="#f1f5f9"/><text x={x-16} y={h-padB+24} className="axis-text">{fmt(hVal,0)}</text></g> })}
    <line x1={padL} y1={padT} x2={padL} y2={h-padB} stroke="#94a3b8"/><line x1={padL} y1={h-padB} x2={w-padR} y2={h-padB} stroke="#94a3b8"/>
    {domeClosed.length ? <polygon points={pth(domeClosed)} className="dome-fill" /> : null}
    {dome?.liquid?.length ? <polyline points={pth(dome.liquid)} className="dome-line liquid" /> : null}
    {dome?.vapor?.length ? <polyline points={pth(dome.vapor)} className="dome-line vapor" /> : null}
    {baseCycle.length ? <polyline points={pth(baseCycle)} fill="none" stroke="#64748b" strokeWidth="3" strokeDasharray="10 7" opacity="0.9" /> : null}
    <polyline points={pth(cycle)} className="cycle-line" />
    {baseline?.points?.map((p) => { const x=sx(p.h_kJ_kg), y=sy(p.P_kPa); return <g key={`b-${p.label}`}>
      <circle cx={x} cy={y} r="6.5" fill="#ffffff" stroke="#475569" strokeWidth="2.2" />
      <text x={x+10} y={y-10} className="point-small" style={{fill:'#475569'}}>K{p.label}</text>
    </g> })}
    {frame.points.map((p) => { const [ox, oy] = offsets[p.label] ?? [14, -20]; const x=sx(p.h_kJ_kg), y=sy(p.P_kPa); const tx=x+ox, ty=y+oy; return <g key={p.label}>
      <line x1={x} y1={y} x2={tx + (ox < 0 ? 72 : 0)} y2={ty+8} stroke="#94a3b8" strokeDasharray="4 4" />
      <circle cx={x} cy={y} r="9" fill={colors[p.label] ?? '#334155'} stroke="#fff" strokeWidth="3"/>
      <rect x={tx-6} y={ty-18} width="100" height="36" rx="9" fill="white" stroke="#cbd5e1" opacity=".96" />
      <text x={tx} y={ty-2} className="point-label">{p.label}</text><text x={tx+28} y={ty-2} className="point-small">{fmt(p.T_C,1)}°C</text>
      <text x={tx} y={ty+13} className="point-small">h={fmt(p.h_kJ_kg,1)}</text>
    </g> })}
    <g>
      <rect x={w-274} y={42} width="226" height="56" rx="12" fill="#ffffff" stroke="#dbe4ee" opacity=".96" />
      <line x1={w-258} y1="61" x2={w-222} y2="61" stroke="#22c55e" strokeWidth="4" />
      <text x={w-214} y="65" className="point-small">AC + HWST</text>
      <line x1={w-258} y1="82" x2={w-222} y2="82" stroke="#64748b" strokeWidth="4" strokeDasharray="10 7" />
      <text x={w-214} y="86" className="point-small">AC konvensional</text>
    </g>
    <text x={w/2} y={h-18} textAnchor="middle" className="axis-title">Entalpi, h (kJ/kg)</text>
    <text transform={`translate(18 ${h/2}) rotate(-90)`} textAnchor="middle" className="axis-title">Tekanan, P (kPa abs, log)</text>
    <text x={padL} y="32" className="system-title">t = {fmt(frame.time_min,2)} menit</text>
    <text x={w-padR} y="32" textAnchor="end" className="component-caption">HWST: 1 → 2 → 2' → 3 → 4 → 1 | Konvensional: 1 → 2 → 3 → 4 → 1</text>
  </svg></div>
}

function PHStateTable({ frame, baseline }: { frame: PhFrame; baseline?: PhFrame }) {
  const baseMap = new Map((baseline?.points ?? []).map((p) => [p.label, p]))
  return <div className="ph-state-panel"><h3>State titik P-h pembanding</h3><p>Kolom HWST menunjukkan siklus AC + HWST. Kolom konvensional adalah pembanding tanpa HWST; titik 2' hanya ada pada sistem HWST.</p><table><thead><tr><th>Titik</th><th>Nama</th><th>HWST h</th><th>HWST P</th><th>HWST T</th><th>Konv. h</th><th>Konv. P</th><th>Konv. T</th></tr></thead><tbody>{frame.points.map(p => { const b = baseMap.get(p.label); return <tr key={p.label}><td><strong>{p.label}</strong></td><td>{p.name}</td><td>{fmt(p.h_kJ_kg,2)}</td><td>{fmt(p.P_kPa,1)}</td><td>{fmt(p.T_C,1)}</td><td>{b ? fmt(b.h_kJ_kg,2) : '-'}</td><td>{b ? fmt(b.P_kPa,1) : '-'}</td><td>{b ? fmt(b.T_C,1) : '-'}</td></tr>})}</tbody></table></div>
}

function NeedRunPanel({ title, onRun, loading }: { title: string; onRun: () => void; loading: boolean }) { return <section className="single-page"><div className="panel need-run"><h2>{title}</h2><p>Jalankan simulasi terlebih dahulu agar data time-series, titik state, dan diagram bergerak dapat ditampilkan.</p><button className="primary" onClick={onRun} disabled={loading}>{loading ? 'Menjalankan...' : 'Jalankan Simulasi'}</button></div></section> }
function Badge({ children }: { children: any }) { return <span className="badge">{children}</span> }

function CoilUsagePanel({ results }: { results: SimulationResults | null }) {
  const rows = results?.coil_usage ?? []
  const baseRows = results?.coil_usage_conventional ?? []
  const summary = results?.summary_values ?? {}
  const conditions = results?.condition_rows ?? []
  const groupsHwst = ['HWST', 'Kondensor', 'Evaporator']
  const groupsBase = ['Kondensor', 'Evaporator']
  const detailFor = (system: string, component: string) => {
    if (component === 'Kondensor') return `Subcool: ${conditionMetric(conditions, system, 'Subcool')}`
    if (component === 'Evaporator') return `Superheat: ${conditionMetric(conditions, system, 'Superheat')}`
    if (component === 'HWST') return 'Mode: desuperheater'
    return undefined
  }
  return <div className="panel coil-panel">
    <div className="panel-title horizontal">
      <div><h2>Persentase Penggunaan Coil</h2><p>Perbandingan zona coil AC + HWST dan AC konvensional dengan solver yang sama.</p></div>
      {results && <div className="coil-meta"><span>DSH = {String(summary.t_dsh_start_min ?? '-')}–{String(summary.t_dsh_end_min ?? '-')} min</span><strong>Best DSH: {String(summary.bestCOP_AC_dsh ?? '-')}</strong></div>}
    </div>
    {!rows.length ? <div className="empty-state">Persentase coil akan muncul setelah simulasi dijalankan.</div> : <>
      <h3 className="coil-section-title">AC + HWST</h3>
      <div className="coil-grid">{groupsHwst.map((group) => <CoilDonut key={'hwst-'+group} title={group} rows={rows.filter((row) => row.komponen === group)} mode="hwst" detail={detailFor('AC + HWST', group)} />)}</div>
      {!!baseRows.length && <>
        <h3 className="coil-section-title">AC Konvensional</h3>
        <div className="coil-grid coil-grid-conventional">{groupsBase.map((group) => <CoilDonut key={'base-'+group} title={group} rows={baseRows.filter((row) => row.komponen === group)} mode="baseline" detail={detailFor('AC Konvensional', group)} />)}</div>
      </>}
    </>}
  </div>
}

function CoilDonut({ title, rows, mode = 'hwst', detail }: { title: string; rows: CoilUsageRow[]; mode?: 'hwst' | 'baseline'; detail?: string }) {
  const valueOf = (row: CoilUsageRow) => Number(mode === 'baseline' ? row.persentase_steady : row.persentase_COP_best_DSH)
  const activeRows = rows.filter((row) => valueOf(row) > 0.0001)
  let angle = 0
  const colorMap: Record<string, string> = { DSH: '#dc2626', TP: '#f59e0b', SC: '#2563eb', SH: '#ef4444' }
  const gradient = activeRows.map((row) => { const start = angle, end = angle + valueOf(row) * 3.6; angle = end; return `${colorMap[row.zona] ?? '#64748b'} ${start}deg ${end}deg` }).join(', ')
  return <div className="coil-card">
    <div className="donut-wrap"><div className="donut" style={{ background: `conic-gradient(${gradient || '#e2e8f0 0deg 360deg'})` }}><div className="donut-hole"><strong>{title}</strong><span>coil</span></div></div></div>
    <div className="coil-legend">{rows.map((row) => { const val = valueOf(row); return <div className="legend-row" key={`${title}-${mode}-${row.zona}`}><span className="legend-dot" style={{ background: colorMap[row.zona] ?? '#64748b' }} /><strong>{row.zona}</strong><em>{val.toFixed(2)}%</em>{mode === 'hwst' && <small>akhir: {Number(row.persentase_akhir ?? 0).toFixed(2)}%</small>}</div> })}</div>
    {detail && <div className="coil-detail-pill">{detail}</div>}
  </div>
}


function conditionMetric(rows: Array<Record<string, string | number | null>>, system: string, keyword: string) {
  const row = rows.find((item) => String(item.sistem ?? '') === system && String(item.parameter ?? '').toLowerCase().includes(keyword.toLowerCase()))
  if (!row) return '- K'
  return `${fmt(row.nilai, 2)} ${String(row.unit ?? '').trim() || 'K'}`
}

function DataTables({ results }: { results: SimulationResults | null }) {
  if (!results) return <div className="panel"><h2>Data Hasil</h2><div className="empty-state">Belum ada data. Jalankan simulasi terlebih dahulu.</div></div>
  return <div className="tables-grid">
    <TableCard title="Ringkasan" rows={results.summary_rows} />
    <TableCard title="Kondisi Refrigeran" rows={results.condition_rows ?? []} note="Superheat dan subcool hasil untuk AC + HWST dan baseline konvensional." />
    <TableCard title="Pressure Drop" rows={results.pressure_drop_rows ?? []} note="DP tetap dihitung; jika feedback aktif dan aman, DP mengoreksi tekanan efektif siklus." />
    <TableCard title="Perpindahan Panas" rows={results.heat_transfer_rows ?? []} note="Nilai h udara/air, U zona, dan UA efektif hasil model." />
    <TableCard title="Persentase Coil AC + HWST" rows={results.coil_usage} note="Nilai utama diambil pada kondisi COP best DSH; kolom akhir adalah kondisi saat simulasi selesai." />
    <TableCard title="Persentase Coil AC Konvensional" rows={results.coil_usage_conventional ?? []} note="Baseline dihitung dengan solver komponen yang sama tanpa HWST." />
    <TableCard title="Validasi Siklus" rows={results.validation_rows ?? []} note="Status validasi rinci disimpan di Excel." />
    <TableCard title="Asumsi Model" rows={results.assumption_rows ?? []} note="Asumsi utama yang dipakai agar klaim simulasi tetap jelas." />
    <TableCard title="State Refrigeran" rows={results.state_rows} />
    <TableCard title="Geometri" rows={results.geometry_rows} />
    <TableCard title="Analisis" rows={results.analysis_rows} />
    <TableCard title="Data Waktu" rows={results.time_series.slice(0, 20)} note="Ditampilkan 20 baris pertama. Data lengkap ada di export Excel." />
  </div>
}

function TableCard({ title, rows, note }: { title: string; rows: Array<Record<string, unknown>>; note?: string }) {
  const headers = rows.length ? Object.keys(rows[0]) : []
  return <div className="panel table-card"><h2>{title}</h2>{note && <p className="note">{note}</p>}<div className="table-scroll"><table><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.map((row, idx) => <tr key={idx}>{headers.map((header) => <td key={header}>{String(row[header] ?? '-')}</td>)}</tr>)}</tbody></table></div></div>
}

function num(v: unknown, fallback = 0) { const n = Number(v); return Number.isFinite(n) ? n : fallback }
function finite(v: unknown) { const n = Number(v); return Number.isFinite(n) ? n : null }
function clamp(n: number, min = 0, max = 1) { return Math.max(min, Math.min(max, n)) }
function frac(v: unknown) { const n = finite(v); if (n === null) return 0; return clamp(n > 1 ? n / 100 : n, 0, 1) }
function pct(v: unknown) { return frac(v) * 100 }
function fmt(v: unknown, nd = 2) { const n = Number(v); return Number.isFinite(n) ? n.toFixed(nd) : '-' }
function formatHMS(minutes: number) { const m = Number.isFinite(minutes) ? Math.max(0, minutes) : 0; const h = Math.floor(m / 60); const mn = Math.floor(m % 60); const s = Math.floor((m * 60) % 60); return `${String(h).padStart(2,'0')}:${String(mn).padStart(2,'0')}:${String(s).padStart(2,'0')}` }
function tempColor(t: number) { const r = Math.max(0, Math.min(1, (t - 0) / 90)); const hue = 210 - r * 210; return `hsl(${hue} 78% 48%)` }

type ZoneSegment = { key: string; label?: string; value: number; color: string; pct?: number }
function zoneColor(zone: string) { const map: Record<string,string> = { DSH:'#ef4444', TP:'#f59e0b', SC:'#84cc16', SH:'#60a5fa' }; return map[zone] ?? '#64748b' }
function zoneTriplet(dsh: unknown, tp: unknown, sc: unknown): ZoneSegment[] { return [
  { key: 'DSH', value: pct(dsh), color: zoneColor('DSH') },
  { key: 'TP', value: pct(tp), color: zoneColor('TP') },
  { key: 'SC', value: pct(sc), color: zoneColor('SC') },
] }
function zonePair(tp: unknown, sh: unknown): ZoneSegment[] { return [
  { key: 'TP', value: pct(tp), color: '#2563eb' },
  { key: 'SH', value: pct(sh), color: zoneColor('SH') },
] }
function normalizeSegments(zones: ZoneSegment[]) {
  const valid = zones.map((z) => ({ ...z, value: Math.max(0, num(z.value)) })).filter((z) => z.value > 0.0001)
  const total = valid.reduce((sum, z) => sum + z.value, 0)
  return total > 0 ? valid.map((z) => ({ ...z, pct: z.value / total * 100 })) : []
}
function SegmentedPath({ d, zones, strokeWidth, fallbackColor }: { d: string; zones: ZoneSegment[]; strokeWidth: number; fallbackColor: string }) {
  const segs = normalizeSegments(zones)
  let start = 0
  return <g className="segmented-coil">
    <path d={d} fill="none" stroke="#cbd5e1" strokeWidth={strokeWidth + 1.8} strokeLinecap="round" strokeLinejoin="round" />
    {!segs.length && <path d={d} fill="none" stroke={fallbackColor} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />}
    {segs.map((seg) => {
      const current = start
      start += seg.pct ?? 0
      return <path key={seg.key} d={d} fill="none" stroke={seg.color} strokeWidth={strokeWidth} strokeLinecap="butt" strokeLinejoin="round" pathLength={100} strokeDasharray={`${Math.max(seg.pct ?? 0, 0.001)} ${Math.max(0, 100 - (seg.pct ?? 0))}`} strokeDashoffset={-current} />
    })}
  </g>
}

function SegmentedPathOnly({ d, zones, strokeWidth, fallbackColor }: { d: string; zones: ZoneSegment[]; strokeWidth: number; fallbackColor: string }) {
  const segs = normalizeSegments(zones)
  let start = 0
  return <g>
    {!segs.length && <path d={d} fill="none" stroke={fallbackColor} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />}
    {segs.map((seg) => {
      const current = start
      start += seg.pct ?? 0
      return <path key={seg.key} d={d} fill="none" stroke={seg.color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" pathLength={100} strokeDasharray={`${Math.max(seg.pct ?? 0, 0.001)} ${Math.max(0, 100 - (seg.pct ?? 0))}`} strokeDashoffset={-current} />
    })}
  </g>
}



type PressureDropInfo = { hwst: number; cond: number; evap: number; high: number; low: number; total: number; capAvailable: number | null; capRequired: number | null }
function pressureDrops(row: TimeRow): PressureDropInfo {
  const hwst = finite(row.DP_HWST_kPa ?? row.DP_hwst_kPa) ?? 0
  const cond = finite(row.DP_cond_kPa ?? row.DP_COND_kPa) ?? 0
  const evap = finite(row.DP_evap_kPa ?? row.DP_EVAP_kPa) ?? 0
  const high = finite(row.DP_high_side_kPa ?? row.DP_high_kPa ?? row.DP_total_high_kPa) ?? Math.max(0, hwst + cond)
  const low = finite(row.DP_low_side_kPa ?? row.DP_low_kPa ?? row.DP_total_low_kPa) ?? Math.max(0, evap)
  const capAvailable = finite(row.capillary_DP_available_kPa)
  const capRequired = finite(row.capillary_DP_required_kPa)
  const totalExplicit = finite(row.DP_total_kPa ?? row.pressure_drop_total_kPa)
  const total = totalExplicit ?? Math.max(0, high) + Math.max(0, low)
  return { hwst, cond, evap, high, low, total, capAvailable, capRequired }
}
function PressureBadge({ x, y, label, value }: { x: number; y: number; label: string; value: number | null | undefined }) {
  if (!Number.isFinite(Number(value))) return null
  return <g className="dp-badge" transform={`translate(${x},${y})`}>
    <rect x="0" y="0" width="96" height="30" rx="9" fill="#ffffff" stroke="#dbe4ee" opacity=".96" />
    <text x="10" y="12">{label}</text>
    <text x="10" y="25" className="val">{fmt(value,1)} kPa</text>
  </g>
}

export default App
