import { useEffect, useMemo, useRef, useState } from 'react'
import { api, waitJob } from '../api.js'
import { Legend, LineChart, Scatter } from '../components/charts.jsx'
import { CloseIcon, DownIcon, DownloadIcon, LinearIcon, PlusIcon, UpIcon } from '../components/Icons.jsx'
import { ErrorBox, Loading, PageHead, Progress, Segmented } from '../components/ui.jsx'
import { downloadFile, fixed, ms, num, toCsv } from '../lib/format.js'
import { useRequest } from '../lib/useRequest.js'
import { useContinuous } from '../state/continuous.jsx'
import { useMeta } from '../state/meta.jsx'

const SHORT = { weighted_sum: 'Зважена сума', ideal_point: 'Тихонова', eps_constraint: 'ε-обмежень', lexicographic: 'Поступки', goal_programming: 'Цільове' }

function Model({ analysis }) {
  const { state, dispatch } = useContinuous()
  const edit = (list, index, patch) => dispatch({ type: 'edit', list, index, patch })
  return (
    <section className="card" style={{ flex: '1 1 380px', maxWidth: 480, minWidth: 0 }} aria-labelledby="model-h">
      <h2 id="model-h">Модель</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span className="caps">Змінні та межі</span>
        {state.variables.map((v, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '80px minmax(0, 1fr) minmax(0, 1fr) 36px', gap: 6, alignItems: 'center' }}>
            <input className="input mono" aria-label="Ім’я змінної" value={v.name} onChange={(e) => edit('variables', i, { name: e.target.value })} />
            <input className="input mono" aria-label={`Нижня межа ${v.name}`} type="number" value={v.lo} onChange={(e) => edit('variables', i, { lo: e.target.value })} />
            <input className="input mono" aria-label={`Верхня межа ${v.name}`} type="number" value={v.hi} onChange={(e) => edit('variables', i, { hi: e.target.value })} />
            <button type="button" className="icon-btn" aria-label={`Видалити змінну ${v.name}`} disabled={state.variables.length <= 1}
              onClick={() => dispatch({ type: 'remove', list: 'variables', index: i })}><CloseIcon /></button>
          </div>
        ))}
        <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }}
          onClick={() => dispatch({ type: 'add', list: 'variables', item: { name: `x${state.variables.length + 1}`, lo: 0, hi: 10 } })}><PlusIcon />Змінна</button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <span className="caps">Цілі</span>
        {state.objectives.map((o, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 12, borderRadius: 12, background: 'var(--ground)' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) auto 36px', gap: 8, alignItems: 'center' }}>
              <input className="input" aria-label="Назва цілі" value={o.name} onChange={(e) => edit('objectives', i, { name: e.target.value })} style={{ fontWeight: 600 }} />
              <Segmented label={`Напрям: ${o.name}`} value={o.sense} onChange={(s) => edit('objectives', i, { sense: s })}
                options={[{ value: 'max', label: '↑ max' }, { value: 'min', label: '↓ min' }]} />
              <button type="button" className="icon-btn" aria-label={`Видалити ціль ${o.name}`} disabled={state.objectives.length <= 2}
                onClick={() => dispatch({ type: 'remove', list: 'objectives', index: i })}><CloseIcon /></button>
            </div>
            <input className="input mono" aria-label={`Формула цілі ${o.name}`} value={o.expr} onChange={(e) => edit('objectives', i, { expr: e.target.value })} />
            <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13 }}>Вага
              <input type="range" min="0" max="1" step="0.05" value={o.weight} style={{ flex: 1 }} onChange={(e) => edit('objectives', i, { weight: Number(e.target.value) })} />
              <output className="mono" style={{ width: 40, textAlign: 'right' }}>{fixed(Number(o.weight), 2)}</output>
            </label>
          </div>
        ))}
        <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }} disabled={state.objectives.length >= 6}
          onClick={() => dispatch({ type: 'add', list: 'objectives', item: { name: `f${state.objectives.length + 1}`, expr: state.variables[0]?.name || 'x1', sense: 'min', weight: 0.5 } })}><PlusIcon />Ціль</button>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span className="caps">Обмеження</span>
        {state.constraints.map((c, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '64px minmax(0, 1fr) 36px', gap: 6, alignItems: 'center' }}>
            <input className="input mono" aria-label="Ліва частина обмеження" value={c.expr} onChange={(e) => edit('constraints', i, { expr: e.target.value })}
              style={{ gridColumn: '1 / -1' }} />
            <select className="select" aria-label="Знак" value={c.op} onChange={(e) => edit('constraints', i, { op: e.target.value })}>
              <option>≤</option><option>≥</option><option>=</option>
            </select>
            <input className="input mono" aria-label="Права частина" type="number" value={c.rhs} onChange={(e) => edit('constraints', i, { rhs: e.target.value })} />
            <button type="button" className="icon-btn" aria-label="Видалити обмеження" onClick={() => dispatch({ type: 'remove', list: 'constraints', index: i })}><CloseIcon /></button>
          </div>
        ))}
        <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }}
          onClick={() => dispatch({ type: 'add', list: 'constraints', item: { expr: state.variables.map((v) => v.name).join(' + '), op: '≤', rhs: 10 } })}><PlusIcon />Обмеження</button>
        <span className="muted" style={{ fontSize: 12 }}>Формули: + − * / ^, дужки, sin, cos, exp, log, sqrt, abs, pi.</span>
      </div>
      {analysis && !analysis.linear && (
        <label className="field">
          <span style={{ display: 'flex', justifyContent: 'space-between' }}>Стартових точок SLSQP<output className="mono">{state.starts}</output></span>
          <input type="range" min="1" max="30" value={state.starts} onChange={(e) => dispatch({ type: 'setStarts', starts: Number(e.target.value) })} />
        </label>
      )}
      {analysis && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="caps">Таблиця виграшів</span>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th scope="col"><span className="sr-only">Оптимум</span></th>{analysis.objectives.map((o) => <th key={o.name} scope="col" className="num">{o.name}</th>)}</tr></thead>
              <tbody>
                {analysis.payoff.map((row) => (
                  <tr key={row.optimum_of}>
                    <th scope="row" style={{ fontWeight: 500, fontSize: 13, color: 'var(--ink)' }}>оптимум «{row.optimum_of}»</th>
                    {analysis.objectives.map((o) => <td key={o.name} className="num" style={{ fontWeight: o.name === row.optimum_of ? 700 : 400 }}>{num(row.values[o.name], 3)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}

function MethodParams({ analysis }) {
  const { state, dispatch } = useContinuous()
  const p = state.params[state.method] || {}
  const set = (name, value) => dispatch({ type: 'setParam', method: state.method, name, value })
  const names = state.objectives.map((o) => o.name)
  if (state.method === 'ideal_point') {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Метрика p</span>
        <Segmented label="Параметр метрики p" value={p.p ?? 'inf'} onChange={(v) => set('p', v)}
          options={[{ value: 1, label: '1' }, { value: 2, label: '2' }, { value: 'inf', label: '∞ (Чебишова)' }]} />
      </div>
    )
  }
  if (state.method === 'eps_constraint') {
    const main = p.main && names.includes(p.main) ? p.main : names[0]
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
        <label className="field">Головна ціль
          <select className="select" value={main} onChange={(e) => set('main', e.target.value)}>{names.map((n) => <option key={n}>{n}</option>)}</select>
        </label>
        {state.objectives.filter((o) => o.name !== main).map((o) => {
          const mid = analysis ? (analysis.ideal[o.name] + analysis.nadir[o.name]) / 2 : 0
          return (
            <label key={o.name} className="field">ε для «{o.name}» ({o.sense === 'max' ? '≥' : '≤'})
              <input className="input mono" type="number" value={p.eps?.[o.name] ?? Number(mid.toFixed(3))}
                onChange={(e) => set('eps', { ...(p.eps || {}), [o.name]: Number(e.target.value) })} />
            </label>
          )
        })}
      </div>
    )
  }
  if (state.method === 'lexicographic') {
    const order = (p.order || names).filter((n) => names.includes(n)).concat(names.filter((n) => !(p.order || names).includes(n)))
    const move = (i, d) => {
      const next = [...order]
      ;[next[i], next[i + d]] = [next[i + d], next[i]]
      set('order', next)
    }
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
        <ol className="order-list">
          {order.map((n, i) => (
            <li key={n}>
              <span className="grow" style={{ fontSize: 13 }}>{i + 1}. {n}</span>
              <button type="button" className="icon-btn" aria-label={`Підняти ${n}`} disabled={i === 0} onClick={() => move(i, -1)}><UpIcon /></button>
              <button type="button" className="icon-btn" aria-label={`Опустити ${n}`} disabled={i === order.length - 1} onClick={() => move(i, 1)}><DownIcon /></button>
            </li>
          ))}
        </ol>
        <label className="field">
          <span style={{ display: 'flex', justifyContent: 'space-between' }}>Поступка δ<output className="mono">{fixed(p.concession ?? 0.1, 2)}</output></span>
          <input type="range" min="0" max="1" step="0.01" value={p.concession ?? 0.1} onChange={(e) => set('concession', Number(e.target.value))} />
        </label>
      </div>
    )
  }
  if (state.method === 'goal_programming') {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
        {state.objectives.map((o) => (
          <label key={o.name} className="field">Ціль для «{o.name}»
            <input className="input mono" type="number" value={p.targets?.[o.name] ?? (analysis ? Number(analysis.ideal[o.name].toFixed(3)) : '')}
              onChange={(e) => set('targets', { ...(p.targets || {}), [o.name]: Number(e.target.value) })} />
          </label>
        ))}
      </div>
    )
  }
  return <span className="muted" style={{ fontSize: 13 }}>Ваги цілей задаються в моделі ліворуч.</span>
}

function solveParams(state, analysis) {
  const p = { ...(state.params[state.method] || {}) }
  const names = state.objectives.map((o) => o.name)
  if (state.method === 'ideal_point') return { p: p.p ?? 'inf' }
  if (state.method === 'eps_constraint') {
    const main = p.main && names.includes(p.main) ? p.main : names[0]
    const eps = {}
    for (const o of state.objectives) {
      if (o.name === main) continue
      eps[o.name] = p.eps?.[o.name] ?? (analysis ? (analysis.ideal[o.name] + analysis.nadir[o.name]) / 2 : 0)
    }
    return { main, eps }
  }
  if (state.method === 'lexicographic') return { order: (p.order || names).filter((n) => names.includes(n)), concession: p.concession ?? 0.1 }
  if (state.method === 'goal_programming') {
    if (!p.targets) return {}
    return { targets: Object.fromEntries(Object.entries(p.targets).filter(([k]) => names.includes(k))) }
  }
  return {}
}

function FrontSection({ analysis, solution }) {
  const { state, dispatch, problem, fingerprint } = useContinuous()
  const { meta } = useMeta()
  const f = state.front
  const names = state.objectives.map((o) => o.name)
  const sync = f.method !== 'nsga2'
  const auto = useRequest((signal) => api.front({ problem, method: f.method, points: f.points }, signal),
    `${fingerprint}|${f.method}|${f.points}`, { enabled: sync && Boolean(analysis), delay: 500 })
  const [nsga, setNsga] = useState({ result: null, job: null, error: null, key: null })
  const ctrl = useRef(null)
  useEffect(() => () => ctrl.current?.abort(), [])
  const runNsga = async () => {
    ctrl.current?.abort()
    ctrl.current = new AbortController()
    const key = `${fingerprint}|${JSON.stringify(f.nsga)}`
    setNsga({ result: null, job: { progress: 0, status: 'queued' }, error: null, key })
    try {
      const started = await api.frontJob({ problem, method: 'nsga2', nsga: f.nsga })
      const result = await waitJob(started, { signal: ctrl.current.signal, onProgress: (job) => setNsga((s) => ({ ...s, job })) })
      setNsga({ result, job: null, error: null, key })
    } catch (e) {
      if (e.name !== 'AbortError') setNsga({ result: null, job: null, error: e, key })
    }
  }
  const front = sync ? auto.data : nsga.key === `${fingerprint}|${JSON.stringify(f.nsga)}` ? nsga.result : null
  const [axes, setAxes] = useState([0, 1])
  const ix = Math.min(axes[0], names.length - 1)
  const iy = Math.min(axes[1], names.length - 1)
  const [nx, ny] = [names[ix], names[iy]]
  const senses = state.objectives.map((o) => o.sense)

  const chart = useMemo(() => {
    if (!front || !analysis || !nx || !ny || nx === ny) return null
    const pts = front.points.map((p, i) => ({ id: `p${i}`, name: `точка ${i + 1}`, x: p.f[nx], y: p.f[ny], kind: 'front' }))
    const line = names.length === 2 ? [...pts].sort((a, b) => a.x - b.x).map((p) => [p.x, p.y]) : null
    const extra = [
      { id: 'ideal', name: 'ідеальна точка', x: analysis.ideal[nx], y: analysis.ideal[ny], kind: 'ideal' },
      { id: 'nadir', name: 'надир', x: analysis.nadir[nx], y: analysis.nadir[ny], kind: 'nadir' },
    ]
    if (front.compromise) {
      const c = front.points[front.compromise.point]
      extra.push({ id: 'comp', name: 'компроміс TOPSIS', x: c.f[nx], y: c.f[ny], kind: 'compromise' })
    }
    if (solution) extra.push({ id: 'sol', name: 'розв’язок методу', x: solution.f[nx], y: solution.f[ny], kind: 'chosen' })
    return { pts: [...pts, ...extra], line }
  }, [front, analysis, solution, nx, ny, names.length])

  const comp = front?.compromise ? front.points[front.compromise.point] : null
  return (
    <section className="card" aria-labelledby="front-h">
      <div className="card-head">
        <div>
          <h2 id="front-h">Фронт Парето</h2>
          <div className="card-sub">{front ? `${front.title} · ${front.points.length} точок · ${ms(front.elapsed_ms)}` : 'усі компроміси між цілями'}</div>
        </div>
        <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>Побудова
          <select className="select" value={f.method} onChange={(e) => dispatch({ type: 'setFront', patch: { method: e.target.value } })}>
            {(meta?.fronts || []).map((m) => <option key={m.key} value={m.key}>{m.title}</option>)}
          </select>
        </label>
      </div>
      {sync ? (
        <label className="field">
          <span style={{ display: 'flex', justifyContent: 'space-between' }}>Кількість точок<output className="mono">{f.points}</output></span>
          <input type="range" min="5" max={analysis?.linear ? 200 : 60} step="1" value={f.points}
            onChange={(e) => dispatch({ type: 'setFront', patch: { points: Number(e.target.value) } })} />
        </label>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
            {[['pop_size', 'Розмір популяції', 20, 400, 10], ['generations', 'Поколінь', 10, 500, 10], ['pc', 'Імовірність схрещування', 0.5, 1, 0.05],
              ['eta_c', 'Індекс SBX ηc', 2, 40, 1], ['eta_m', 'Індекс мутації ηm', 2, 60, 1]].map(([k, label, min, max, step]) => (
              <label key={k} className="field">
                <span style={{ display: 'flex', justifyContent: 'space-between' }}>{label}<output className="mono">{num(f.nsga[k])}</output></span>
                <input type="range" min={min} max={max} step={step} value={f.nsga[k]}
                  onChange={(e) => dispatch({ type: 'setFront', patch: { nsga: { [k]: Number(e.target.value) } } })} />
              </label>
            ))}
            <label className="field">Seed
              <input className="input mono" type="number" min="0" value={f.nsga.seed}
                onChange={(e) => dispatch({ type: 'setFront', patch: { nsga: { seed: Math.max(0, Number(e.target.value) || 0) } } })} />
            </label>
          </div>
          <button type="button" className="btn primary" style={{ alignSelf: 'flex-start' }} onClick={runNsga} disabled={Boolean(nsga.job)}>
            {nsga.job ? 'Обчислюю…' : 'Запустити NSGA-II'}
          </button>
          {nsga.job && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Progress value={nsga.job.progress} label="Прогрес NSGA-II" />
              <span className="muted" style={{ fontSize: 13 }}>{nsga.job.message || 'у черзі'}</span>
            </div>
          )}
        </div>
      )}
      <ErrorBox error={sync ? auto.error : nsga.error} />
      {sync && !front && !auto.error && <Loading>Будую фронт…</Loading>}
      {names.length > 2 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
          {['X', 'Y'].map((a, k) => (
            <label key={a} className="field">Вісь {a}
              <select className="select" value={axes[k]} onChange={(e) => setAxes(k === 0 ? [Number(e.target.value), axes[1]] : [axes[0], Number(e.target.value)])}>
                {names.map((n, i) => <option key={n} value={i}>{n}</option>)}
              </select>
            </label>
          ))}
        </div>
      )}
      {chart && (
        <>
          <Scatter points={chart.pts} line={chart.line} height={300} xLabel={nx} yLabel={ny}
            xHint={senses[ix] === 'max' ? '→ краще' : '← краще'} yHint={senses[iy] === 'max' ? 'вище – краще' : 'нижче – краще'}
            label={`Фронт Парето з ${front.points.length} точок у просторі цілей ${nx} і ${ny}`} />
          <Legend items={[{ label: 'фронт Парето', color: '#0F7C7E', round: true }, { label: 'ідеальна точка', color: '#2E8B57' },
            { label: 'надир', color: '#5B6673' }, { label: 'компроміс TOPSIS', color: '#2F5D9E', round: true }, { label: 'розв’язок методу', color: '#E0922F', round: true }]} />
          {names.length > 2 && <p className="note">Задача має {names.length} цілі – показано проєкцію фронту на дві вибрані.</p>}
        </>
      )}
      {comp && (
        <p className="note">
          Рекомендований компроміс на фронті: {Object.entries(comp.x).map(([k, v]) => `${k} = ${num(v, 3)}`).join(', ')} →{' '}
          {Object.entries(comp.f).map(([k, v]) => `${k} = ${num(v, 3)}`).join(', ')}
        </p>
      )}
      {front?.convergence && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="caps">Збіжність NSGA-II (гіпероб’єм)</span>
          <LineChart xs={front.convergence.map((_, i) => i + 1)} height={160} label="Гіпероб’єм фронту за поколіннями"
            series={[{ name: 'гіпероб’єм', values: front.convergence, color: '#0F7C7E' }]} xLabel="покоління" />
        </div>
      )}
      {front && front.points.length > 0 && (
        <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }}
          onClick={() => {
            const vars = state.variables.map((v) => v.name)
            downloadFile('pareto_front.csv', toCsv(front.points.map((p) => ({ ...p.x, ...p.f })), [...vars, ...names]), 'text/csv')
          }}><DownloadIcon />Точки фронту (CSV)</button>
      )}
    </section>
  )
}

export default function ContinuousPage() {
  const { state, dispatch, problem, fingerprint } = useContinuous()
  const { meta } = useMeta()
  const [examples, setExamples] = useState([])
  const [loadError, setLoadError] = useState(null)
  useEffect(() => {
    api.examples().then(setExamples).catch(setLoadError)
  }, [])
  useEffect(() => {
    if (!state.exampleId) api.example('production').then((ex) => dispatch({ type: 'loadExample', example: ex })).catch(setLoadError)
  }, [state.exampleId, dispatch])

  const ready = state.variables.length > 0 && state.objectives.length >= 2
  const analyzed = useRequest((signal) => api.analyze(problem, signal), fingerprint, { enabled: ready, delay: 400 })
  const analysis = analyzed.error ? null : analyzed.data
  const params = solveParams(state, analysis)
  const solved = useRequest((signal) => api.contSolve({ problem, method: state.method, params }, signal),
    `${fingerprint}|${state.method}|${JSON.stringify(params)}`, { enabled: ready && Boolean(analysis), delay: 300 })
  const sol = solved.error ? null : solved.data

  return (
    <>
      <PageHead eyebrow="Неперервна задача" title={state.title || 'Неперервна задача'}>
        {analysis && (
          <span className="pill accent"><LinearIcon />{analysis.linear ? 'Лінійна задача · точний симплекс-метод' : `Нелінійна задача · ${analysis.solver}`}</span>
        )}
      </PageHead>
      <ErrorBox error={loadError} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {examples.map((ex) => (
          <button key={ex.id} type="button" className="choice" aria-pressed={state.exampleId === ex.id}
            onClick={() => api.example(ex.id).then((e) => dispatch({ type: 'loadExample', example: e })).catch(setLoadError)}>
            {ex.title}
          </button>
        ))}
        <button type="button" className="choice" aria-pressed={state.exampleId === 'custom'} onClick={() => dispatch({ type: 'blank' })}>+ Власна задача</button>
      </div>
      {state.description && <p className="note">{state.description}</p>}
      <div className="row">
        <Model analysis={analysis} />
        <div className="col-main">
          <ErrorBox error={analyzed.error} />
          <section className="card" aria-labelledby="sol-h">
            <div className="card-head">
              <h2 id="sol-h">Компроміс</h2>
              <Segmented label="Метод" value={state.method} onChange={(m) => dispatch({ type: 'setMethod', method: m })}
                options={(meta?.continuous || []).map((m) => ({ value: m.key, label: SHORT[m.key] || m.title }))} />
            </div>
            <MethodParams analysis={analysis} />
            <ErrorBox error={solved.error} />
            {!sol && !solved.error && !analyzed.error && <Loading />}
            {sol && (
              <>
                <div className="metrics" style={{ opacity: solved.loading ? 0.7 : 1 }}>
                  {Object.entries(sol.x).map(([k, v]) => (
                    <div key={k} className="metric"><span className="label">{k}</span><b>{num(v, 3)}</b></div>
                  ))}
                  {Object.entries(sol.f).map(([k, v]) => (
                    <div key={k} className="metric dark">
                      <span className="label">{k}{analysis ? ` · ідеал ${num(analysis.ideal[k], 3)}` : ''}</span><b>{num(v, 3)}</b>
                    </div>
                  ))}
                </div>
                <span className="muted" style={{ fontSize: 13 }}>{sol.title} · {ms(sol.elapsed_ms)}{sol.violation > 1e-6 ? ` · порушення обмежень ${fixed(sol.violation, 6)}` : ''}</span>
              </>
            )}
          </section>
          {analysis && <FrontSection analysis={analysis} solution={sol} />}
        </div>
      </div>
    </>
  )
}
