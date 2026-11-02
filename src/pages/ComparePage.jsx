import { api } from '../api.js'
import { Heatmap } from '../components/charts.jsx'
import { StarIcon } from '../components/Icons.jsx'
import Stepper from '../components/Stepper.jsx'
import { ErrorBox, Loading, NeedData, PageHead } from '../components/ui.jsx'
import { corrColor, fixed, ms } from '../lib/format.js'
import { useRequest } from '../lib/useRequest.js'
import { useProblem } from '../state/problem.jsx'

// Короткі підписи стовпців матриці кореляції (повні назви – у рядках)
const CODES = { weighted_sum: 'ЗС', ideal_point: 'ІТ', topsis: 'TOPSIS', pareto: 'Пар.', germeier: 'Герм.',
  lexicographic: 'Лекс.', vikor: 'VIKOR', weighted_product: 'Мульт.' }

// Колір місця: 1 – темний бірюзовий, далі світліше
function rankColor(rank, n) {
  const t = (rank - 1) / Math.max(n - 1, 1)
  const l = Math.round(30 + t * 64)
  return { bg: `hsl(181 70% ${l}%)`, fg: l < 55 ? '#FFFFFF' : '#16202B' }
}

export default function ComparePage() {
  const { state, used, problem, fingerprint } = useProblem()
  const res = useRequest((signal) => api.compare({ problem }, signal), fingerprint, { enabled: Boolean(problem) && used.length >= 2 })
  if (!state.table) {
    return (<><PageHead eyebrow="Дискретний вибір · крок 5" title="Чи згодні між собою методи" /><Stepper current="compare" /><NeedData /></>)
  }
  const c = res.data
  const top = c ? c.alternatives.slice(0, 10) : []
  const maxBorda = c ? Math.max(...c.alternatives.map((a) => a.borda)) : 1
  const n = c ? c.alternatives.length : 1
  return (
    <>
      <PageHead eyebrow={`Дискретний вибір · ${state.table.title} · крок 5`} title="Чи згодні між собою методи" />
      <Stepper current="compare" />
      <ErrorBox error={res.error} />
      {!c && !res.error && <Loading>Запускаю всі методи…</Loading>}
      {c && (
        <>
          <section className="card rec">
            <div className="rec-main">
              <span className="pill"><StarIcon />Консенсус {c.methods.length} методів</span>
              <h2 style={{ margin: 0 }}>{c.consensus.name}</h2>
              <p style={{ margin: 0, color: 'var(--muted)', fontSize: 14 }}>
                Сума балів Борда (m − місце) за всіма методами з однаковими вагами. Методи з порогами (головний критерій,
                цільове програмування) не входять у порівняння.
              </p>
            </div>
            <div className="rec-score">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <small>Балів Борда</small><span className="big">{c.consensus.borda}</span>
                <small>з {(n - 1) * c.methods.length} можливих</small>
              </div>
            </div>
          </section>
          <section className="card" aria-labelledby="ranks-h">
            <div className="card-head">
              <h2 id="ranks-h">Місця 10 кращих альтернатив</h2>
              <span className="muted" style={{ fontSize: 13 }}>1 – найкраще місце</span>
            </div>
            <Heatmap label="Таблиця місць альтернатив за кожним методом" rows={top.map((a) => a.name)} cols={c.methods.map((m) => m.abbr)}
              values={top.map((a) => c.methods.map((m) => a.ranks[m.key]))} color={(v) => rankColor(v, n)} format={(v) => v} />
          </section>
          <div className="grid-2">
            <section className="card" aria-labelledby="borda-h">
              <h2 id="borda-h">Бали Борда</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {top.map((a, i) => (
                  <div key={a.index} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.2fr) 40px', gap: 10, alignItems: 'center', fontSize: 13 }}>
                    <span style={{ fontWeight: i === 0 ? 700 : 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={a.name}>{a.name}</span>
                    <div className="track" style={{ height: 10, borderRadius: 5, background: 'var(--track)' }}>
                      <div style={{ height: 10, borderRadius: 5, width: `${(a.borda / maxBorda) * 100}%`, background: i === 0 ? 'var(--best)' : 'var(--accent)' }} />
                    </div>
                    <span className="mono" style={{ textAlign: 'right' }}>{a.borda}</span>
                  </div>
                ))}
              </div>
            </section>
            <section className="card" aria-labelledby="corr-h">
              <div>
                <h2 id="corr-h">Рангова кореляція Спірмена</h2>
                <div className="card-sub">1 – методи ранжують однаково, 0 – незалежно, «–» – метод не розрізняє альтернатив</div>
              </div>
              <Heatmap label="Матриця кореляції Спірмена між методами" rows={c.methods.map((m) => m.abbr)}
                cols={c.methods.map((m) => CODES[m.key] || m.abbr)}
                values={c.spearman} color={corrColor} format={(v) => (v === null ? '–' : fixed(v, 2))} minCell={44} />
            </section>
          </div>
          <section className="card" aria-labelledby="time-h">
            <h2 id="time-h">Час розрахунку</h2>
            <div className="metrics">
              {c.methods.map((m) => (
                <div key={m.key} className="metric"><span className="label">{m.abbr}</span><b style={{ fontSize: 20 }}>{ms(m.elapsed_ms)}</b></div>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  )
}
