import { DownIcon, UpIcon } from './Icons.jsx'
import { Segmented } from './ui.jsx'
import { fixed } from '../lib/format.js'

const CHOICE_LABELS = { inf: '∞', minmax: 'min–max', linear_max: 'x / max' }
const choiceLabel = (o) => CHOICE_LABELS[o] ?? String(o).replace('.', ',')

// Форма параметрів методу, побудована за описом з реєстру API (GET /api/methods)
export default function ParamsForm({ spec, values, criteria, onChange }) {
  if (!spec?.params?.length) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {spec.params.map((p) => {
        const v = values[p.name]
        if (p.kind === 'choice') {
          return (
            <div key={p.name} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{p.label}</span>
              <Segmented label={p.label} fill value={v ?? p.default} onChange={(x) => onChange(p.name, x)}
                options={p.options.map((o) => ({ value: o, label: choiceLabel(o) }))} />
              {p.help && <span className="muted" style={{ fontSize: 12 }}>{p.help}</span>}
            </div>
          )
        }
        if (p.kind === 'float') {
          const val = v ?? p.default
          return (
            <label key={p.name} className="field">
              <span style={{ display: 'flex', justifyContent: 'space-between' }}>{p.label}<output className="mono">{fixed(val, 2)}</output></span>
              <input type="range" min={p.min} max={p.max} step={p.step} value={val} onChange={(e) => onChange(p.name, Number(e.target.value))} />
              {p.help && <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>{p.help}</span>}
            </label>
          )
        }
        if (p.kind === 'criterion') {
          return (
            <label key={p.name} className="field">{p.label}
              <select className="select" value={v ?? ''} onChange={(e) => onChange(p.name, e.target.value || null)}>
                <option value="">найважливіший за вагою</option>
                {criteria.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
              </select>
            </label>
          )
        }
        if (p.kind === 'order') {
          const order = (v && v.length ? v : [...criteria].sort((a, b) => b.weight - a.weight).map((c) => c.name))
            .filter((n) => criteria.some((c) => c.name === n))
          const full = order.concat(criteria.map((c) => c.name).filter((n) => !order.includes(n)))
          const move = (i, d) => {
            const next = [...full]
            ;[next[i], next[i + d]] = [next[i + d], next[i]]
            onChange(p.name, next)
          }
          return (
            <div key={p.name} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{p.label}</span>
              <ol className="order-list">
                {full.map((n, i) => (
                  <li key={n}>
                    <span className="grow" style={{ fontSize: 13 }}>{i + 1}. {n}</span>
                    <button type="button" className="icon-btn" aria-label={`Підняти ${n}`} disabled={i === 0} onClick={() => move(i, -1)}><UpIcon /></button>
                    <button type="button" className="icon-btn" aria-label={`Опустити ${n}`} disabled={i === full.length - 1} onClick={() => move(i, 1)}><DownIcon /></button>
                  </li>
                ))}
              </ol>
            </div>
          )
        }
        if (p.kind === 'per_criterion') {
          const dict = v || {}
          return (
            <div key={p.name} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{p.label}</span>
              {p.help && <span className="muted" style={{ fontSize: 12 }}>{p.help}</span>}
              {criteria.map((c) => (
                <label key={c.name} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 120px', gap: 8, alignItems: 'center', fontSize: 13 }}>
                  <span>{c.name} <span className="muted">{c.sense === 'max' ? '≥' : '≤'}</span></span>
                  <input className="input mono" inputMode="decimal" value={dict[c.name] ?? ''} placeholder={p.name === 'targets' ? 'авто' : 'немає'}
                    onChange={(e) => {
                      const next = { ...dict }
                      if (e.target.value.trim() === '') delete next[c.name]
                      else next[c.name] = e.target.value      // рядок; у число перетворюється перед запитом
                      onChange(p.name, Object.keys(next).length ? next : null)
                    }} />
                </label>
              ))}
            </div>
          )
        }
        return null
      })}
    </div>
  )
}
