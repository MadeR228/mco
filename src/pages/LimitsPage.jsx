import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { ArrowIcon, CloseIcon, PlusIcon, WarnIcon } from '../components/Icons.jsx'
import Stepper from '../components/Stepper.jsx'
import { ErrorBox, Loading, NeedData, PageHead, Progress, Segmented } from '../components/ui.jsx'
import { num } from '../lib/format.js'
import { useRequest } from '../lib/useRequest.js'
import { useMeta } from '../state/meta.jsx'
import { useProblem } from '../state/problem.jsx'

const HINTS = {
  '≤': 'не більше', '≥': 'не менше', '<': 'менше', '>': 'більше', '=': 'дорівнює', '≠': 'не дорівнює',
  'у списку': 'одне зі значень через кому', 'не у списку': 'жодне зі значень через кому', 'містить': 'текст містить фрагмент',
}

function Editor() {
  const { state, dispatch } = useProblem()
  const { meta } = useMeta()
  const t = state.table
  const [column, setColumn] = useState(t.numeric_columns[0] || t.columns[0])
  const [op, setOp] = useState('≤')
  const [value, setValue] = useState('')
  const isNumeric = t.numeric_columns.includes(column)
  // підказки значень для текстових стовпців (бренд, тип, магазин)
  const options = useMemo(() => {
    if (isNumeric) return []
    return [...new Set(t.records.map((r) => r[column]).filter((v) => v !== null && v !== undefined && v !== ''))].slice(0, 50)
  }, [t.records, column, isNumeric])
  const range = useMemo(() => {
    if (!isNumeric) return null
    const v = t.records.map((r) => r[column]).filter((x) => typeof x === 'number')
    return v.length ? [Math.min(...v), Math.max(...v)] : null
  }, [t.records, column, isNumeric])
  const add = (e) => {
    e.preventDefault()
    if (!value.trim()) return
    dispatch({ type: 'addConstraint', constraint: { column, op, value: value.trim() } })
    setValue('')
  }
  return (
    <section className="card col-side" style={{ flex: '1 1 380px', maxWidth: 460 }} aria-labelledby="lim-h">
      <div>
        <h2 id="lim-h">Умови</h2>
        <div className="card-sub">Альтернатива бере участь у виборі, лише якщо виконує всі умови</div>
      </div>
      <div className="chips">
        {state.constraints.length === 0 && <span className="muted" style={{ fontSize: 14 }}>Умов немає – беруть участь усі альтернативи</span>}
        {state.constraints.map((c, i) => (
          <span key={`${c.column}${c.op}${c.value}${i}`} className="chip">
            {c.column} {c.op} {c.value}
            <button type="button" className="icon-btn" aria-label={`Видалити умову ${c.column} ${c.op} ${c.value}`}
              onClick={() => dispatch({ type: 'removeConstraint', index: i })}><CloseIcon /></button>
          </span>
        ))}
      </div>
      <div className="divider" />
      <form onSubmit={add} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <span className="caps">Нова умова</span>
        <label className="field">Стовпець
          <select className="select" value={column} onChange={(e) => { setColumn(e.target.value); setValue('') }}>
            {t.columns.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.3fr)', gap: 8 }}>
          <label className="field">Умова
            <select className="select" value={op} onChange={(e) => setOp(e.target.value)}>
              {(meta?.operators || ['≤', '≥']).map((o) => <option key={o} value={o}>{o} – {HINTS[o]}</option>)}
            </select>
          </label>
          <label className="field">Значення
            <input className={`input${isNumeric ? ' mono' : ''}`} value={value} onChange={(e) => setValue(e.target.value)}
              list={options.length ? 'limit-values' : undefined} inputMode={isNumeric ? 'decimal' : undefined}
              placeholder={range ? `${num(range[0])} – ${num(range[1])}` : 'значення'} />
            {options.length > 0 && (
              <datalist id="limit-values">{options.map((o) => <option key={String(o)} value={String(o)} />)}</datalist>
            )}
          </label>
        </div>
        <button type="submit" className="btn primary" style={{ alignSelf: 'flex-start' }} disabled={!value.trim()}><PlusIcon />Додати умову</button>
      </form>
      <p className="note">Приклади: «Ціна, грн ≤ 70000», «Тип не у списку Ігровий», «Бренд у списку Apple, Lenovo», «Модель містить Pro».</p>
    </section>
  )
}

function Result() {
  const { state, dispatch, problem, fingerprint, used, gaps } = useProblem()
  const feas = useRequest((signal) => api.feasibility(problem, signal), fingerprint, { enabled: used.length >= 2 })
  const f = feas.data
  return (
    <div className="col-main">
      {gaps.rows > 0 && (
        <div className="alert warn">
          <WarnIcon />
          <span className="grow"><b>{gaps.rows} альтернатив</b> без значень критеріїв: {gaps.columns.join(', ')}</span>
          <Segmented label="Обробка пропусків" value={state.missing} onChange={(m) => dispatch({ type: 'setMissing', missing: m })}
            options={[{ value: 'drop', label: 'Виключити' }, { value: 'median', label: 'Медіана' }]} />
        </div>
      )}
      {used.length < 2 && <div className="alert warn"><span className="grow">Виберіть щонайменше два критерії на кроці «Критерії й ваги».</span></div>}
      <ErrorBox error={feas.error} />
      {used.length >= 2 && !f && !feas.error && <Loading>Перевіряю умови…</Loading>}
      {f && (
        <>
          <section className="card" aria-labelledby="feas-h" style={{ opacity: feas.loading ? 0.7 : 1 }}>
            <h2 id="feas-h">Беруть участь у виборі</h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '4px 12px' }}>
              <span className="mono" style={{ fontSize: 44, fontWeight: 600, lineHeight: 1 }}>{f.feasible}</span>
              <span className="muted" style={{ fontSize: 15 }}>з {f.total} альтернатив · Парето-оптимальних {f.pareto} · виключено {f.excluded.length}</span>
            </div>
            <Progress value={f.feasible / f.total} label="Частка допустимих альтернатив" />
          </section>
          <section className="card" aria-labelledby="excl-h">
            <h2 id="excl-h">Чому виключено</h2>
            {f.excluded.length === 0 ? <span className="muted">Усі альтернативи задовольняють умови</span> : (
              <div className="table-wrap" style={{ maxHeight: 520, overflowY: 'auto' }}>
                <table className="data">
                  <thead><tr><th scope="col">Альтернатива</th><th scope="col">Порушені умови</th></tr></thead>
                  <tbody>
                    {f.excluded.map((e) => (
                      <tr key={e.index}>
                        <td className="name">{e.name}</td>
                        <td style={{ color: 'var(--muted-dark)' }}>{e.reasons.join('; ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}

export default function LimitsPage() {
  const { state } = useProblem()
  if (!state.table) {
    return (<><PageHead eyebrow="Дискретний вибір · крок 3" title="Що точно не підходить" /><Stepper current="limits" /><NeedData /></>)
  }
  return (
    <>
      <PageHead eyebrow={`Дискретний вибір · ${state.table.title} · крок 3`} title="Що точно не підходить">
        <Link to="/discrete/solution" className="btn primary">Показати розв’язок <ArrowIcon /></Link>
      </PageHead>
      <Stepper current="limits" />
      <div className="row">
        <Editor />
        <Result />
      </div>
    </>
  )
}
