import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, waitJob } from '../api.js'
import { ArrowIcon, DownloadIcon, WarnIcon } from '../components/Icons.jsx'
import Stepper from '../components/Stepper.jsx'
import { ErrorBox, Loading, PageHead, Progress, Segmented } from '../components/ui.jsx'
import { downloadFile, num, toCsv } from '../lib/format.js'
import { useProblem } from '../state/problem.jsx'

const SOURCES = [
  { key: 'example', title: 'Приклад', text: 'ноутбуки, смартфони, знімки каталогів' },
  { key: 'shop', title: 'Інтернет-магазин', text: 'актуальні ціни й характеристики' },
  { key: 'file', title: 'Власний файл', text: 'CSV, Excel або збережена сторінка' },
]

function ExamplePicker({ onLoad, busy }) {
  const [list, setList] = useState(null)
  const [error, setError] = useState(null)
  const { state } = useProblem()
  useEffect(() => {
    api.datasets().then(setList).catch(setError)
  }, [])
  if (error) return <ErrorBox error={error} />
  if (!list) return <Loading>Завантажую список…</Loading>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {list.map((d) => (
        <button key={d.id} type="button" className="choice" style={{ minHeight: 56 }} disabled={busy}
          aria-pressed={state.table?.datasetId === d.id} onClick={() => onLoad(() => api.dataset(d.id), { source: 'example', datasetId: d.id })}>
          <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>{d.title}</span>
            <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 400 }}>{d.note}</span>
          </span>
          <span className={`tag${d.kind === 'snapshot' ? '' : ' best'}`}>{d.kind === 'snapshot' ? 'реальні дані' : `${d.rows}`}</span>
        </button>
      ))}
    </div>
  )
}

function FileInput({ accept, label, onFile, busy }) {
  const ref = useRef(null)
  return (
    <label className="field">
      {label}
      <input ref={ref} type="file" accept={accept} disabled={busy} className="input" style={{ paddingTop: 8 }}
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
          e.target.value = ''
        }} />
    </label>
  )
}

function ShopPicker({ onTable, onError }) {
  const [shops, setShops] = useState(null)
  const [shop, setShop] = useState('brain')
  const [pages, setPages] = useState(2)
  const [cache, setCache] = useState(true)
  const [job, setJob] = useState(null)
  const [log, setLog] = useState([])
  const ctrl = useRef(null)
  useEffect(() => {
    api.shops().then(setShops).catch(onError)
    return () => ctrl.current?.abort()
  }, [onError])
  if (!shops) return <Loading>Завантажую список магазинів…</Loading>
  const current = shops.find((s) => s.id === shop)
  const running = job && (job.status === 'queued' || job.status === 'running')

  async function load() {
    onError(null)
    ctrl.current?.abort()
    ctrl.current = new AbortController()
    setLog([])
    try {
      const started = await api.loadShop(shop, { pages, use_cache: cache })
      const table = await waitJob(started, { signal: ctrl.current.signal, onProgress: setJob })
      setLog(table.log || [])
      onTable(table, { source: 'shop', shop })
    } catch (e) {
      if (e.name !== 'AbortError') onError(e)
      setJob(null)
    }
  }

  return (
    <>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {shops.map((s) => (
          <button key={s.id} type="button" className="choice" style={{ minHeight: 56 }} aria-pressed={s.id === shop}
            onClick={() => setShop(s.id)} disabled={running}>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 15, fontWeight: 600 }}>{s.title.split(' (')[0]}</span>
              <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 400 }}>
                {s.live ? `${s.page_size} товарів на сторінці` : 'збережена сторінка каталогу'}
              </span>
            </span>
            <span className={`tag${s.live ? '' : ' best'}`}>{s.live ? 'з сайту' : 'HTML-файл'}</span>
          </button>
        ))}
      </div>
      {current?.live ? (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>Сторінок каталогу</span>
            <div role="group" aria-label="Кількість сторінок" className="segmented" style={{ alignItems: 'center' }}>
              <button type="button" aria-label="Менше сторінок" onClick={() => setPages((p) => Math.max(1, p - 1))}
                style={{ width: 40, background: '#fff', fontSize: 18 }} disabled={running}>−</button>
              <output className="mono" style={{ width: 40, textAlign: 'center', fontWeight: 600 }}>{pages}</output>
              <button type="button" aria-label="Більше сторінок" onClick={() => setPages((p) => Math.min(10, p + 1))}
                style={{ width: 40, background: '#fff', fontSize: 18 }} disabled={running}>+</button>
            </div>
          </div>
          <label className="check">
            <input type="checkbox" checked={cache} onChange={(e) => setCache(e.target.checked)} disabled={running} />
            Брати збережені сторінки (до 24 год)
          </label>
          <button type="button" className="btn primary" style={{ minHeight: 48 }} onClick={load} disabled={running}>
            {running ? 'Завантажую…' : 'Завантажити каталог'}
          </button>
          {running && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Progress value={job.progress} label="Прогрес завантаження" />
              <span className="muted" style={{ fontSize: 13 }}>{job.message || 'у черзі'}</span>
            </div>
          )}
          {log.length > 0 && (
            <ul className="note" style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
              {log.map((l) => <li key={l} style={{ overflowWrap: 'anywhere' }}><span style={{ color: 'var(--accent-strong)', fontWeight: 700 }}>✓</span> {l}</li>)}
            </ul>
          )}
          <p className="note">Програма читає robots.txt сайту, робить не більше одного запиту за 2 с і зберігає сторінки на добу.</p>
        </>
      ) : (
        <>
          <p className="note">{current?.note}</p>
          <FileInput accept=".html,.htm" label="Збережена сторінка каталогу Rozetka"
            onFile={async (f) => {
              onError(null)
              try {
                onTable(await api.upload(f), { source: 'shop', shop })
              } catch (e) {
                onError(e)
              }
            }} />
        </>
      )}
    </>
  )
}

function Preview() {
  const { state, dispatch, used, gaps } = useProblem()
  const t = state.table
  if (!t) {
    return (
      <section className="card col-main">
        <h2>Дані ще не вибрано</h2>
        <p className="note">Виберіть приклад, завантажте каталог магазину або власний файл – тут з’явиться таблиця альтернатив.</p>
      </section>
    )
  }
  const cols = [t.name_column, ...(used.length ? used.map((c) => c.name) : t.numeric_columns)].filter(Boolean).slice(0, 9)
  const rows = t.records.slice(0, 12)
  return (
    <section className="card col-main" aria-labelledby="preview-h">
      <div className="card-head">
        <div>
          <h2 id="preview-h">Отримано {t.rows} альтернатив</h2>
          <div className="card-sub">{t.title}{t.note ? ` · ${t.note}` : ''}</div>
        </div>
        <button type="button" className="btn small" onClick={() => downloadFile('alternatives.csv', toCsv(t.records, t.columns), 'text/csv')}>
          <DownloadIcon />CSV
        </button>
      </div>
      {gaps.rows > 0 && (
        <div className="alert warn">
          <WarnIcon />
          <span className="grow"><b>{gaps.rows} альтернатив</b> без значень: {gaps.columns.join(', ')}</span>
          <Segmented label="Обробка пропусків" value={state.missing} onChange={(m) => dispatch({ type: 'setMissing', missing: m })}
            options={[{ value: 'drop', label: 'Виключити' }, { value: 'median', label: 'Медіана' }]} />
        </div>
      )}
      <div className="table-wrap">
        <table className="data" style={{ minWidth: 720 }}>
          <thead>
            <tr>{cols.map((c) => <th key={c} scope="col" className={t.numeric_columns.includes(c) ? 'num' : ''}>{c}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {cols.map((c) => {
                  const v = r[c]
                  const isNum = t.numeric_columns.includes(c)
                  const empty = v === null || v === undefined
                  return (
                    <td key={c} className={`${isNum ? 'num' : ''}${empty && isNum ? ' gap' : ''}`} style={c === t.name_column ? { fontWeight: 600 } : undefined}>
                      {empty ? (isNum ? 'немає' : '') : isNum ? num(v) : String(v)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {t.rows > rows.length && <span className="muted" style={{ fontSize: 13 }}>Показано {rows.length} з {t.rows}</span>}
      {'Оцінка CPU' in (t.records[0] || {}) && (
        <p className="note">Продуктивність CPU – бали з довідника 150 процесорів; для невідомих моделей – наближена оцінка за сімейством.</p>
      )}
    </section>
  )
}

export default function DataPage() {
  const { state, dispatch } = useProblem()
  const [source, setSource] = useState(state.table?.source || 'example')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const setTable = (table, extra) => dispatch({ type: 'setTable', table: { ...table, ...extra } })
  async function loadWith(fn, extra) {
    setError(null)
    setBusy(true)
    try {
      setTable(await fn(), extra)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHead eyebrow="Дискретний вибір · крок 1" title="Звідки взяти альтернативи">
        {state.table && <Link to="/discrete/criteria" className="btn primary">Далі: критерії <ArrowIcon /></Link>}
      </PageHead>
      <Stepper current="data" />
      <div role="group" aria-label="Джерело даних" className="tiles">
        {SOURCES.map((s) => (
          <button key={s.key} type="button" className="tile" aria-pressed={source === s.key} onClick={() => setSource(s.key)}>
            <strong>{s.title}</strong><span>{s.text}</span>
          </button>
        ))}
      </div>
      <ErrorBox error={error} />
      <div className="row">
        <section className="card col-side" aria-labelledby="source-h">
          <h2 id="source-h">{SOURCES.find((s) => s.key === source).title}</h2>
          {source === 'example' && <ExamplePicker onLoad={loadWith} busy={busy} />}
          {source === 'shop' && <ShopPicker onTable={setTable} onError={setError} />}
          {source === 'file' && (
            <>
              <FileInput accept=".csv,.txt,.xlsx,.xls,.html,.htm" label="Файл з альтернативами" busy={busy}
                onFile={(f) => loadWith(() => api.upload(f), { source: 'file' })} />
              <p className="note">Рядки – альтернативи, стовпці – характеристики. CSV з роздільником «;» і десятковою комою
                (формат Excel) теж читається. HTML – збережена сторінка каталогу Rozetka, Brain або Telemart.</p>
            </>
          )}
          {busy && <Loading>Завантажую…</Loading>}
        </section>
        <Preview />
      </div>
    </>
  )
}
