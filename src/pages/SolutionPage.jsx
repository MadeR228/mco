import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Legend, Scatter, StackBar } from '../components/charts.jsx'
import { CheckIcon, DownloadIcon, StarIcon } from '../components/Icons.jsx'
import ParamsForm from '../components/ParamsForm.jsx'
import Stepper from '../components/Stepper.jsx'
import { ErrorBox, Loading, NeedData, PageHead } from '../components/ui.jsx'
import { colorAt, downloadFile, fixed, ms, num, toCsv } from '../lib/format.js'
import { cleanParams } from '../lib/params.js'
import { useRequest } from '../lib/useRequest.js'
import { useMeta } from '../state/meta.jsx'
import { useProblem } from '../state/problem.jsx'

const GROUPS = [
  { title: 'Згортки', keys: ['weighted_sum', 'weighted_product', 'germeier'] },
  { title: 'Відстань до ідеалу', keys: ['ideal_point', 'topsis', 'vikor'] },
  { title: 'Пороги та пріоритети', keys: ['main_criterion', 'lexicographic', 'goal_programming', 'pareto'] },
]

function MethodPanel({ methods }) {
  const { state, dispatch, used, setParam } = useProblem()
  const spec = methods.find((m) => m.key === state.method)
  return (
    <section className="card col-side" style={{ maxWidth: 340 }} aria-labelledby="method-h">
      <h2 id="method-h">Метод</h2>
      {GROUPS.map((g) => (
        <div key={g.title} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span className="label">{g.title}</span>
          <div className="choice-grid">
            {g.keys.map((k) => {
              const m = methods.find((x) => x.key === k)
              if (!m) return null
              const on = state.method === k
              return (
                <button key={k} type="button" className="choice" aria-pressed={on} onClick={() => dispatch({ type: 'setMethod', method: k })}
                  title={m.title}>
                  {m.abbr}{on && <CheckIcon />}
                </button>
              )
            })}
          </div>
        </div>
      ))}
      <div className="divider" />
      <ParamsForm spec={spec} values={state.params[state.method] || {}} criteria={used}
        onChange={(name, value) => setParam(state.method, name, value)} />
      {spec && (
        <div className="note" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <strong style={{ color: 'var(--ink)' }}>{spec.title}</strong>
          <span>{spec.description}</span>
          {!spec.uses_weights && <em>Ваги цим методом не використовуються.</em>}
        </div>
      )}
    </section>
  )
}

function goodness(alts, higher) {
  const s = alts.map((a) => a.score).filter((x) => x !== null)
  const lo = Math.min(...s)
  const hi = Math.max(...s)
  return (score) => {
    if (score === null) return 0
    if (hi === lo) return 1
    const g = higher ? (score - lo) / (hi - lo) : (hi - score) / (hi - lo)
    return 0.08 + 0.92 * g
  }
}

function pareto2d(points, sx, sy) {
  return points.map((p) => !points.some((q) => q !== p && q.x * sx >= p.x * sx && q.y * sy >= p.y * sy
    && (q.x * sx > p.x * sx || q.y * sy > p.y * sy)))
}

function MethodInfo({ result }) {
  const i = result.info || {}
  if (result.method === 'vikor' && i.compromise) {
    const good = i.C1 && i.C2
    return (
      <div className={`alert ${good ? 'ok' : 'warn'}`}>
        <span className="grow">Умови VIKOR: прийнятна перевага C1 – {i.C1 ? 'так' : 'ні'}, стабільність C2 – {i.C2 ? 'так' : 'ні'}.
          Компромісна множина: {i.compromise.join(', ')}</span>
      </div>
    )
  }
  const text = {
    main_criterion: i.feasible !== undefined && `Пороги задовольняють ${i.feasible} альтернатив; головний критерій – «${i.main}».`,
    lexicographic: i.remaining_after_step && `Залишилось після кроків: ${i.remaining_after_step.join(' → ')} (порядок: ${(i.order || []).join(', ')}).`,
    goal_programming: i.goals && `Найкраща альтернатива досягає ${result.alternatives[0]?.goals_achieved ?? 0} з ${i.goals} цілей.`,
    germeier: result.alternatives[0]?.weakest && `Найслабший критерій лідера – «${result.alternatives[0].weakest}».`,
    pareto: i.pareto_count && `Множина Парето – ${i.pareto_count} альтернатив, шарів недомінованості – ${i.fronts}.`,
  }[result.method]
  return text ? <p className="note">{text}</p> : null
}

export default function SolutionPage() {
  const { state, used, problem, fingerprint } = useProblem()
  const { meta, error: metaError } = useMeta()
  const params = cleanParams(state.params[state.method])
  const enabled = Boolean(problem) && used.length >= 2
  const solved = useRequest((signal) => api.solve({ problem, method: state.method, params }, signal),
    `${fingerprint}|${state.method}|${JSON.stringify(params)}`, { enabled })
  const consensus = useRequest((signal) => api.compare({ problem }, signal), fingerprint, { enabled, delay: 600 })
  const [showAll, setShowAll] = useState(false)
  const minCrit = used.find((c) => c.sense === 'min')?.name || used[0]?.name
  const maxCrit = used.find((c) => c.sense === 'max' && c.name !== minCrit)?.name || used[1]?.name
  const [axes, setAxes] = useState({})
  const ax = { x: used.some((c) => c.name === axes.x) ? axes.x : minCrit, y: used.some((c) => c.name === axes.y) ? axes.y : maxCrit }

  const r = solved.data
  const scatter = useMemo(() => {
    if (!r || !ax.x || !ax.y) return null
    const sx = used.find((c) => c.name === ax.x)?.sense === 'max' ? 1 : -1
    const sy = used.find((c) => c.name === ax.y)?.sense === 'max' ? 1 : -1
    const pts = r.alternatives.map((a) => ({ id: a.index, name: a.name, x: a.values[ax.x], y: a.values[ax.y] }))
    const front = pareto2d(pts, sx, sy)
    pts.forEach((p, i) => { p.kind = p.id === r.best?.index ? 'best' : front[i] ? 'pareto' : 'dom' })
    const line = pts.filter((_, i) => front[i]).sort((a, b) => a.x - b.x).map((p) => [p.x, p.y])
    return { pts, line, sx, sy, count: line.length }
  }, [r, ax.x, ax.y, used])

  if (!state.table) {
    return (<><PageHead eyebrow="Дискретний вибір" title="Який варіант обрати" /><Stepper current="solution" /><NeedData /></>)
  }
  const methods = meta?.discrete || []
  const best = r?.alternatives.find((a) => a.index === r.best?.index)
  const g = r ? goodness(r.alternatives, r.higher_is_better) : null
  const rows = r ? (showAll ? r.alternatives : r.alternatives.slice(0, 8)) : []
  const tableCols = used.slice(0, 4).map((c) => c.name)
  const top3 = r ? r.alternatives.slice(0, 3) : []
  const other = consensus.data && best && consensus.data.consensus.index !== best.index ? consensus.data.consensus : null

  const exportCsv = () => {
    const cols = ['Місце', 'Альтернатива', 'Оцінка', 'Парето', ...used.map((c) => c.name)]
    downloadFile('mco_results.csv', toCsv(r.alternatives.map((a) => ({
      'Місце': a.rank, 'Альтернатива': a.name, 'Оцінка': a.score, 'Парето': a.pareto ? 'так' : '',
      ...a.values,
    })), cols), 'text/csv')
  }
  const exportJson = () => downloadFile('mco_problem.json', JSON.stringify({
    dataset: state.table.title, criteria: used, constraints: state.constraints, missing: state.missing,
    method: state.method, params: r?.params ?? params, best: r?.best,
  }, null, 2), 'application/json')

  return (
    <>
      <PageHead eyebrow={`Дискретний вибір · ${state.table.title}`} title="Який варіант обрати">
        <button type="button" className="btn" onClick={exportJson}>Зберегти постановку</button>
        <button type="button" className="btn primary" onClick={exportCsv} disabled={!r}><DownloadIcon />Експорт результатів</button>
      </PageHead>
      <Stepper current="solution" />
      <ErrorBox error={metaError} />
      {used.length < 2 && <div className="alert warn"><span className="grow">Виберіть щонайменше два критерії на кроці «Критерії й ваги».</span></div>}
      <div className="row">
        {methods.length > 0 && <MethodPanel methods={methods} />}
        <div className="col-main">
          <ErrorBox error={solved.error} />
          {!r && !solved.error && <Loading />}
          {r && best && (
            <section className="card rec" aria-labelledby="rec-h" style={{ opacity: solved.loading ? 0.7 : 1 }}>
              <div className="rec-main">
                <span id="rec-h" className="pill"><StarIcon />Рекомендація</span>
                <h2 style={{ margin: 0 }}>{best.name}</h2>
                <div className="chips">
                  {used.slice(0, 6).map((c) => <span key={c.name} className="spec"><b>{num(best.values[c.name])}</b> {c.name.replace(/,.*$/, '')}</span>)}
                </div>
                <MethodInfo result={r} />
                {other && (
                  <p style={{ margin: 0, fontSize: 14, color: 'var(--muted)' }}>
                    Інші методи частіше обирають <b style={{ color: 'var(--ink)' }}>{other.name}</b> – він лідирує за консенсусом Борда.{' '}
                    <Link to="/discrete/compare">Порівняти методи</Link>
                  </p>
                )}
              </div>
              <div className="rec-score">
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <small>Узагальнений критерій</small>
                  <span className="big">{best.score === null ? '—' : Math.abs(best.score) >= 1000 ? num(best.score) : fixed(best.score, 3)}</span>
                  <small>{r.higher_is_better ? 'більше – краще' : 'менше – краще'}</small>
                </div>
                <div className="stats">
                  <div><b>{r.counts.feasible}/{r.counts.total}</b><small>допустимі</small></div>
                  <div><b>{r.counts.pareto}</b><small>Парето</small></div>
                  <div><b>{ms(r.elapsed_ms)}</b><small>розрахунок</small></div>
                </div>
              </div>
            </section>
          )}
          {r && (
            <section className="card" aria-labelledby="rank-h">
              <div className="card-head">
                <h2 id="rank-h">Рейтинг альтернатив</h2>
                {r.alternatives.length > 8 && (
                  <button type="button" className="btn small" onClick={() => setShowAll((v) => !v)}>
                    {showAll ? 'Лише перші 8' : `Усі ${r.alternatives.length}`}
                  </button>
                )}
              </div>
              <div className="table-wrap">
                <table className="data" style={{ minWidth: 760 }}>
                  <thead>
                    <tr>
                      <th scope="col">#</th><th scope="col">Альтернатива</th><th scope="col" style={{ width: 220 }}>Оцінка</th>
                      {tableCols.map((c) => <th key={c} scope="col" className="num" title={c}>{c.replace(/,.*$/, '')}</th>)}
                      <th scope="col" style={{ textAlign: 'center' }}>Парето</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((a) => (
                      <tr key={a.index} className={a.index === r.best?.index ? 'best' : ''}>
                        <td className="mono muted">{a.rank}</td>
                        <td className="name">{a.name}</td>
                        <td>
                          <div className="score-bar">
                            <div className="track"><div className={`fill${a.index === r.best?.index ? ' best' : ''}`} style={{ width: `${g(a.score) * 100}%` }} /></div>
                            <span className="mono" style={{ fontSize: 13, width: 64, textAlign: 'right' }}>
                              {a.score === null ? '—' : Math.abs(a.score) >= 1000 ? num(a.score) : fixed(a.score, 3)}
                            </span>
                          </div>
                        </td>
                        {tableCols.map((c) => <td key={c} className="num">{num(a.values[c])}</td>)}
                        <td style={{ textAlign: 'center', color: 'var(--accent-strong)', fontWeight: 700 }}>{a.pareto ? '✓' : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {r && scatter && (
            <div className="grid-2">
              <section className="card" aria-labelledby="pareto-h">
                <div className="card-head">
                  <h2 id="pareto-h">Альтернативи на площині</h2>
                  <span className="muted" style={{ fontSize: 13 }}>Парето за двома критеріями: {scatter.count}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 8 }}>
                  <label className="field">Вісь X
                    <select className="select" value={ax.x} onChange={(e) => setAxes({ ...ax, x: e.target.value })}>
                      {used.map((c) => <option key={c.name}>{c.name}</option>)}
                    </select>
                  </label>
                  <label className="field">Вісь Y
                    <select className="select" value={ax.y} onChange={(e) => setAxes({ ...ax, y: e.target.value })}>
                      {used.map((c) => <option key={c.name}>{c.name}</option>)}
                    </select>
                  </label>
                </div>
                <Scatter points={scatter.pts} line={scatter.line} xLabel={ax.x} yLabel={ax.y}
                  xHint={scatter.sx > 0 ? '→ краще' : '← краще'} yHint={scatter.sy > 0 ? 'вище – краще' : 'нижче – краще'}
                  label={`Діаграма розсіювання ${scatter.pts.length} альтернатив за критеріями ${ax.x} і ${ax.y}; рекомендація ${best?.name}`}
                  labels={best ? [{ text: best.name.split(' ').slice(0, 3).join(' '), x: best.values[ax.x], y: best.values[ax.y] }] : []} />
                <Legend items={[{ label: 'Парето', color: '#0F7C7E', round: true }, { label: 'доміновані', color: '#B9C3CC', round: true },
                  { label: 'рекомендація', color: '#E0922F', round: true }]} />
              </section>
              <section className="card" aria-labelledby="contrib-h">
                <div>
                  <h2 id="contrib-h">З чого складається оцінка</h2>
                  <div className="card-sub">Внесок критеріїв wⱼ·rⱼ для трьох лідерів (r – нормоване значення)</div>
                </div>
                {top3.map((a) => {
                  const parts = used.map((c, i) => ({ label: `${c.name}: ${fixed((r.weights[c.name] || 0) * (a.normalized[c.name] || 0), 3)}`,
                    value: (r.weights[c.name] || 0) * (a.normalized[c.name] || 0), color: colorAt(i) }))
                  const total = parts.reduce((s, p) => s + p.value, 0)
                  return (
                    <div key={a.index} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, gap: 12 }}>
                        <span style={{ fontWeight: 600 }}>{a.name}</span><span className="mono">{fixed(total, 3)}</span>
                      </div>
                      <StackBar parts={parts} label={parts.map((p) => p.label).join(', ')} />
                    </div>
                  )
                })}
                <Legend items={used.map((c, i) => ({ label: `${c.name.replace(/,.*$/, '')} · ${fixed(r.weights[c.name], 2)}`, color: colorAt(i) }))} />
                <Link to="/discrete/sensitivity" style={{ fontSize: 14, fontWeight: 600 }}>Як зміниться вибір, якщо змінити ваги →</Link>
              </section>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
