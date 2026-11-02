import { useState } from 'react'
import { api } from '../api.js'
import { Legend, LineChart } from '../components/charts.jsx'
import Stepper from '../components/Stepper.jsx'
import { ErrorBox, Loading, NeedData, PageHead } from '../components/ui.jsx'
import { colorAt, fixed, pct } from '../lib/format.js'
import { cleanParams } from '../lib/params.js'
import { useRequest } from '../lib/useRequest.js'
import { useMeta } from '../state/meta.jsx'
import { useProblem } from '../state/problem.jsx'

const PLACE_COLORS = ['#0F7C7E', '#2F5D9E', '#E0922F', '#8A5A9E', '#A8C3D3']

export default function SensitivityPage() {
  const { state, used, problem, fingerprint } = useProblem()
  const { meta } = useMeta()
  const spec = meta?.discrete.find((m) => m.key === state.method)
  // метод без ваг (Парето, головний критерій, поступки) – аналізуємо TOPSIS
  const method = spec && !spec.uses_weights ? 'topsis' : state.method
  const params = method === state.method ? cleanParams(state.params[state.method]) : {}
  const heaviest = [...used].sort((a, b) => b.weight - a.weight)[0]?.name
  const [crit, setCrit] = useState(null)
  const criterion = used.some((c) => c.name === crit) ? crit : heaviest
  const [steps, setSteps] = useState(41)
  const [mc, setMc] = useState({ samples: 1000, concentration: 30, seed: 0 })
  const enabled = Boolean(problem) && used.length >= 2 && Boolean(meta)
  const key = `${fingerprint}|${method}|${JSON.stringify(params)}`
  const sweep = useRequest((signal) => api.sensitivity({ problem, method, params, criterion, steps }, signal),
    `${key}|${criterion}|${steps}`, { enabled })
  const carlo = useRequest((signal) => api.montecarlo({ problem, method, params, ...mc }, signal),
    `${key}|${JSON.stringify(mc)}`, { enabled, delay: 400 })

  if (!state.table) {
    return (<><PageHead eyebrow="Дискретний вибір · крок 6" title="Наскільки стійкий вибір" /><Stepper current="sensitivity" /><NeedData /></>)
  }
  const s = sweep.data
  const m = carlo.data
  const methodTitle = meta?.discrete.find((x) => x.key === method)?.title
  return (
    <>
      <PageHead eyebrow={`Дискретний вибір · ${state.table.title} · крок 6`} title="Наскільки стійкий вибір" />
      <Stepper current="sensitivity" />
      {spec && !spec.uses_weights && (
        <p className="note">Вибраний метод «{spec.title}» не використовує ваги, тому чутливість до ваг показано для TOPSIS.</p>
      )}
      <div className="row">
        <section className="card col-side" aria-labelledby="sens-set-h">
          <h2 id="sens-set-h">Чутливість до ваги</h2>
          <label className="field">Критерій
            <select className="select" value={criterion || ''} onChange={(e) => setCrit(e.target.value)}>
              {used.map((c) => <option key={c.name}>{c.name}</option>)}
            </select>
          </label>
          <label className="field">
            <span style={{ display: 'flex', justifyContent: 'space-between' }}>Кроків<output className="mono">{steps}</output></span>
            <input type="range" min="11" max="101" step="10" value={steps} onChange={(e) => setSteps(Number(e.target.value))} />
          </label>
          <span className="muted" style={{ fontSize: 13 }}>Метод: {methodTitle}</span>
          {s && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span className="caps">Зміна переможця</span>
              {s.switches.length === 0 && <span style={{ fontSize: 14 }}>Не змінюється за жодної ваги</span>}
              {s.switches.map((w) => (
                <span key={`${w.weight}${w.to}`} style={{ fontSize: 13 }}>
                  <b className="mono">{fixed(w.weight, 2)}</b>: {w.from} → <b>{w.to}</b>
                </span>
              ))}
            </div>
          )}
        </section>
        <section className="card col-main" aria-labelledby="sens-h">
          <div>
            <h2 id="sens-h">Оцінка альтернатив при зміні ваги «{criterion}»</h2>
            <div className="card-sub">Інші ваги пропорційно ділять залишок · {s ? (s.higher_is_better ? 'більше – краще' : 'менше – краще') : ''}</div>
          </div>
          <ErrorBox error={sweep.error} />
          {!s && !sweep.error && <Loading />}
          {s && (
            <LineChart xs={s.weights} vline={s.current_weight} xLabel={`вага критерію «${s.criterion}», пунктир – поточна (${fixed(s.current_weight, 2)})`}
              label={`Графік чутливості до ваги ${s.criterion}`}
              series={s.series.map((x, i) => ({ name: x.name, values: x.scores, color: colorAt(i) }))} />
          )}
        </section>
      </div>

      <div className="row">
        <section className="card col-side" aria-labelledby="mc-set-h">
          <h2 id="mc-set-h">Монте-Карло</h2>
          <p className="note">Ваги випадково коливаються навколо заданих (розподіл Діріхле). Що більша концентрація, то ближче вони до ваших.</p>
          <label className="field">
            <span style={{ display: 'flex', justifyContent: 'space-between' }}>Випробувань<output className="mono">{mc.samples}</output></span>
            <input type="range" min="100" max="5000" step="100" value={mc.samples} onChange={(e) => setMc({ ...mc, samples: Number(e.target.value) })} />
          </label>
          <label className="field">
            <span style={{ display: 'flex', justifyContent: 'space-between' }}>Концентрація<output className="mono">{mc.concentration}</output></span>
            <input type="range" min="2" max="200" step="1" value={mc.concentration} onChange={(e) => setMc({ ...mc, concentration: Number(e.target.value) })} />
          </label>
          <label className="field">Seed
            <input className="input mono" type="number" min="0" value={mc.seed} onChange={(e) => setMc({ ...mc, seed: Math.max(0, Number(e.target.value) || 0) })} />
          </label>
        </section>
        <section className="card col-main" aria-labelledby="mc-h">
          <div>
            <h2 id="mc-h">Імовірність посісти місце</h2>
            <div className="card-sub">{m ? `${m.samples} наборів випадкових ваг` : ''}</div>
          </div>
          <ErrorBox error={carlo.error} />
          {!m && !carlo.error && <Loading />}
          {m && (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {m.alternatives.slice(0, 8).map((a) => (
                  <div key={a.index} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.6fr) 56px', gap: 10, alignItems: 'center', fontSize: 13 }}>
                    <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.name}>{a.name}</span>
                    <div className="stack" style={{ height: 18 }} role="img"
                      aria-label={a.places.map((p, i) => `${i + 1} місце ${pct(p)}`).join(', ')}>
                      {a.places.map((p, i) => <span key={i} style={{ width: `${p * 100}%`, background: PLACE_COLORS[i] }} />)}
                    </div>
                    <span className="mono" style={{ textAlign: 'right' }}>{pct(a.first, 1)}</span>
                  </div>
                ))}
              </div>
              <Legend items={PLACE_COLORS.map((c, i) => ({ label: `${i + 1} місце`, color: c }))} />
              <p className="note">Найчастіше перша: <b>{m.alternatives[0].name}</b> – {pct(m.alternatives[0].first, 1)} випробувань.</p>
            </>
          )}
        </section>
      </div>
    </>
  )
}
