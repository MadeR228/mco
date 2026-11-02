import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Legend, StackBar } from '../components/charts.jsx'
import { ArrowIcon, DownIcon, UpIcon } from '../components/Icons.jsx'
import Stepper from '../components/Stepper.jsx'
import { ErrorBox, NeedData, OkBox, PageHead, Segmented } from '../components/ui.jsx'
import { colorAt, fixed, num, pct } from '../lib/format.js'
import { useProblem } from '../state/problem.jsx'

const SAATY = [
  { value: 1 / 9, label: '1/9' }, { value: 1 / 7, label: '1/7' }, { value: 1 / 5, label: '1/5' }, { value: 1 / 3, label: '1/3' },
  { value: 1, label: '1' }, { value: 3, label: '3' }, { value: 5, label: '5' }, { value: 7, label: '7' }, { value: 9, label: '9' },
]
const MODES = [
  { value: 'manual', label: 'Вручну' }, { value: 'equal', label: 'Рівні' }, { value: 'ahp', label: 'AHP' },
  { value: 'entropy', label: 'Ентропія' }, { value: 'critic', label: 'CRITIC' }, { value: 'roc', label: 'ROC' },
]

function closestSaaty(ratio) {
  return SAATY.reduce((best, s) => (Math.abs(Math.log(s.value) - Math.log(ratio)) < Math.abs(Math.log(best.value) - Math.log(ratio)) ? s : best)).value
}

function rangeText(records, column) {
  const v = records.map((r) => r[column]).filter((x) => typeof x === 'number')
  if (!v.length) return 'немає значень'
  return `${num(Math.min(...v))} – ${num(Math.max(...v))}`
}

// ---------------------------------------------------------------- AHP
function AhpPanel({ used, onWeights }) {
  const { state, dispatch } = useProblem()
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const names = used.map((c) => c.name)
  const pairs = useMemo(() => names.flatMap((a, i) => names.slice(i + 1).map((b) => [a, b])), [names])
  // початкові судження – з ваг на момент відкриття панелі (далі ваги рахує сам AHP, тож вони не впливають на матрицю)
  const [initial] = useState(() => Object.fromEntries(used.flatMap((a, i) => used.slice(i + 1).map((b) => [
    `${a.name}|${b.name}`, closestSaaty((a.weight || 1) / (b.weight || 1))]))))
  const value = (a, b) => state.ahp[`${a}|${b}`] ?? initial[`${a}|${b}`] ?? 1
  const matrix = names.map((a, i) => names.map((b, j) => (i === j ? 1 : i < j ? value(a, b) : 1 / value(b, a))))
  const key = JSON.stringify(matrix)
  useEffect(() => {
    let alive = true
    api.weights('ahp', { criteria: used.map(({ name, sense, weight }) => ({ name, sense, weight })), matrix: JSON.parse(key) })
      .then((r) => {
        if (!alive) return
        setResult(r)
        setError(null)
        onWeights(r.weights)
      })
      .catch((e) => alive && setError(e))
    return () => {
      alive = false
    }
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <p className="note">Шкала Сааті: 1 – однаково важливі, 3 – помірна, 5 – суттєва, 7 – значна, 9 – абсолютна перевага
        лівого критерію; 1/3 … 1/9 – перевага правого.</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '10px 20px' }}>
        {pairs.map(([a, b]) => (
          <label key={`${a}|${b}`} className="field" style={{ fontWeight: 500 }}>
            <span>{a} <span className="muted">vs</span> {b}</span>
            <select className="select" value={String(value(a, b))}
              onChange={(e) => dispatch({ type: 'setAhp', key: `${a}|${b}`, value: Number(e.target.value) })}>
              {SAATY.map((s) => <option key={s.label} value={String(s.value)}>{s.label}</option>)}
            </select>
          </label>
        ))}
      </div>
      <ErrorBox error={error} />
      {result && (result.consistent
        ? <OkBox title={`Узгодженість: CR = ${fixed(result.cr, 3)}`}>Парні порівняння узгоджені (норма ≤ 0,1)</OkBox>
        : <div className="alert warn"><span className="grow"><b>CR = {fixed(result.cr, 3)}</b> – судження неузгоджені (норма ≤ 0,1). Перегляньте порівняння.</span></div>)}
    </div>
  )
}

// ---------------------------------------------------------------- ROC
function RocPanel({ used, onWeights }) {
  const [order, setOrder] = useState(() => [...used].sort((a, b) => b.weight - a.weight).map((c) => c.name))
  const names = used.map((c) => c.name).join('|')
  const full = order.filter((n) => used.some((c) => c.name === n)).concat(used.map((c) => c.name).filter((n) => !order.includes(n)))
  const key = full.join('|')
  useEffect(() => {
    api.weights('roc', { criteria: used.map(({ name, sense, weight }) => ({ name, sense, weight })), order: full })
      .then((r) => onWeights(r.weights)).catch(() => {})
  }, [key, names]) // eslint-disable-line react-hooks/exhaustive-deps
  const move = (i, d) => {
    const next = [...full]
    ;[next[i], next[i + d]] = [next[i + d], next[i]]
    setOrder(next)
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <span className="label">Від найважливішого до найменш важливого</span>
      <ol className="order-list">
        {full.map((n, i) => (
          <li key={n}>
            <span className="mono muted" style={{ width: 20 }}>{i + 1}</span>
            <span className="grow">{n}</span>
            <button type="button" className="icon-btn" aria-label={`Підняти ${n}`} disabled={i === 0} onClick={() => move(i, -1)}><UpIcon /></button>
            <button type="button" className="icon-btn" aria-label={`Опустити ${n}`} disabled={i === full.length - 1} onClick={() => move(i, 1)}><DownIcon /></button>
          </li>
        ))}
      </ol>
    </div>
  )
}

export default function CriteriaPage() {
  const { state, dispatch, used } = useProblem()
  const [error, setError] = useState(null)

  const mode = state.weightMode
  const usedKey = used.map((c) => `${c.name}:${c.sense}`).join('|')
  useEffect(() => {
    if (!['equal', 'entropy', 'critic'].includes(mode) || used.length < 2) return
    const body = { criteria: used.map(({ name, sense, weight }) => ({ name, sense, weight })) }
    if (mode !== 'equal') body.records = state.table.records
    api.weights(mode, body).then((r) => {
      setError(null)
      dispatch({ type: 'setWeights', weights: r.weights })
    }).catch(setError)
  }, [mode, usedKey]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!state.table) {
    return (<><PageHead eyebrow="Дискретний вибір · крок 2" title="Що для вас важливо" /><Stepper current="criteria" /><NeedData /></>)
  }
  const total = used.reduce((s, c) => s + (c.weight || 0), 0)
  const share = (c) => (total > 0 ? (c.weight || 0) / total : 0)
  const setWeights = (w) => dispatch({ type: 'setWeights', weights: w })

  return (
    <>
      <PageHead eyebrow={`Дискретний вибір · ${state.table.title} · крок 2`} title="Що для вас важливо">
        <Link to="/discrete/limits" className="btn primary">Далі: обмеження <ArrowIcon /></Link>
      </PageHead>
      <Stepper current="criteria" />
      <div className="row">
        <section className="card" style={{ flex: '999 1 560px' }} aria-labelledby="crit-h">
          <div className="card-head">
            <div>
              <h2 id="crit-h">Критерії та ваги</h2>
              <div className="card-sub">Ваги нормуються до суми 1 автоматично</div>
            </div>
            <Segmented label="Спосіб визначення ваг" value={mode} options={MODES}
              onChange={(m) => dispatch({ type: 'setWeightMode', mode: m })} />
          </div>
          <ErrorBox error={error} />
          {used.length < 2 && <div className="alert warn"><span className="grow">Позначте щонайменше два критерії</span></div>}
          <div>
            {state.criteria.map((c) => (
              <div key={c.name} className={`crit-row${c.use ? '' : ' off'}`}>
                <label className="crit-name">
                  <input type="checkbox" checked={c.use}
                    onChange={(e) => dispatch({ type: 'updateCriterion', name: c.name, patch: { use: e.target.checked, weight: c.weight || 0.1 } })} />
                  <span>
                    <span style={{ fontSize: 15, fontWeight: 600 }}>{c.name}</span>
                    <small>{rangeText(state.table.records, c.name)}</small>
                  </span>
                </label>
                <Segmented label={`Напрям: ${c.name}`} value={c.sense}
                  onChange={(s) => dispatch({ type: 'updateCriterion', name: c.name, patch: { sense: s } })}
                  options={[{ value: 'min', label: '↓ min' }, { value: 'max', label: '↑ max' }]} />
                <label className="crit-weight">
                  <span className="sr-only">Вага: {c.name}</span>
                  <input type="range" min="0" max="1" step="0.01" value={c.weight || 0} disabled={!c.use}
                    onChange={(e) => {
                      if (mode !== 'manual') dispatch({ type: 'setWeightMode', mode: 'manual' })
                      dispatch({ type: 'updateCriterion', name: c.name, patch: { weight: Number(e.target.value) } })
                    }} />
                  <output>{c.use ? fixed(share(c), 2) : '—'}</output>
                </label>
              </div>
            ))}
          </div>
          {mode === 'ahp' && used.length >= 2 && <AhpPanel used={used} onWeights={setWeights} />}
          {mode === 'roc' && used.length >= 2 && <RocPanel used={used} onWeights={setWeights} />}
        </section>

        <div style={{ flex: '1 1 340px', maxWidth: 460, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 24 }}>
          <section className="card" aria-labelledby="dist-h">
            <h2 id="dist-h">Розподіл ваг</h2>
            <StackBar height={28} label={used.map((c) => `${c.name} ${pct(share(c))}`).join(', ')}
              parts={used.map((c, i) => ({ label: c.name, value: share(c), color: colorAt(i) }))} />
            <Legend items={used.map((c, i) => ({ label: `${c.name} – ${pct(share(c))}`, color: colorAt(i) }))} />
          </section>
        </div>
      </div>
    </>
  )
}
