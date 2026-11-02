import { useState } from 'react'
import { short, tickLabels, ticks } from '../lib/format.js'

const KIND = {
  best: { color: '#E0922F', ring: '#B36A12', size: 16 },
  pareto: { color: '#0F7C7E', ring: '#0B5E60', size: 12 },
  dom: { color: '#B9C3CC', ring: '#9AA6B1', size: 11 },
  front: { color: '#0F7C7E', ring: '#0F7C7E', size: 9 },
  ideal: { color: '#2E8B57', ring: '#1F6B42', size: 14 },
  nadir: { color: '#5B6673', ring: '#3D4853', size: 12 },
  chosen: { color: '#E0922F', ring: '#B36A12', size: 20 },
  compromise: { color: '#2F5D9E', ring: '#1F3F6E', size: 16 },
}

// Підпис біля точки (x, y у % ширини/висоти) так, щоб він не виходив за межі графіка:
// біля правого краю – ліворуч від точки, біля верхнього – під нею
function labelPlacement(x, y) {
  const horiz = x > 55 ? { right: `calc(${100 - x}% + 10px)` } : { left: `calc(${x}% + 10px)` }
  const vert = y > 80 ? { top: `calc(${100 - y}% + 8px)` } : { bottom: `calc(${y}% + 6px)` }
  return { ...horiz, ...vert }
}

// Підказка над точкою, зсунута всередину графіка біля країв
function tooltipPlacement(x, y) {
  const tx = x < 20 ? '-12px' : x > 80 ? 'calc(-100% + 12px)' : '-50%'
  const ty = y > 80 ? '14px' : 'calc(-100% - 12px)'
  return { left: `${x}%`, top: `${100 - y}%`, transform: `translate(${tx}, ${ty})` }
}

function domain(values) {
  const v = values.filter(Number.isFinite)
  const t = ticks(Math.min(...v), Math.max(...v), 5)
  return { lo: t[0], hi: t[t.length - 1], ticks: t }
}

// Діаграма розсіювання: альтернативи, фронт Парето (ламана), ідеал/надир/вибрана точка
export function Scatter({ points: rawPoints, line: rawLine, xLabel, yLabel, xHint, yHint, height = 260, label, labels = [] }) {
  const [hover, setHover] = useState(null)
  // точки без координат (наприклад, дані попередньої задачі під час перерахунку) не малюються
  const points = rawPoints.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
  const line = rawLine ? rawLine.filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y)) : null
  if (!points.length) return null
  const X = domain(points.map((p) => p.x).concat(line ? line.map((p) => p[0]) : []))
  const Y = domain(points.map((p) => p.y).concat(line ? line.map((p) => p[1]) : []))
  const px = (x) => ((x - X.lo) / (X.hi - X.lo || 1)) * 100
  const py = (y) => ((y - Y.lo) / (Y.hi - Y.lo || 1)) * 100
  const ordered = [...points].sort((a, b) => (KIND[a.kind]?.size || 0) - (KIND[b.kind]?.size || 0))
  return (
    <div>
      <div className="chart">
        <div className="y-axis" aria-hidden="true">
          {tickLabels(Y.ticks).reverse().map((t, i) => <span key={i}>{t}</span>)}
        </div>
        <div className="plot-col">
          <div className="plot" role="img" aria-label={label}
            style={{ height, background: `linear-gradient(#EEF1F4 1px, transparent 1px) 0 0 / 100% ${100 / (Y.ticks.length - 1)}%` }}>
            {line && line.length > 1 && (
              <svg className="lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <polyline fill="none" stroke="#0F7C7E" strokeWidth="1.8" strokeDasharray="4 3" vectorEffect="non-scaling-stroke"
                  points={line.map(([x, y]) => `${px(x)},${100 - py(y)}`).join(' ')} />
              </svg>
            )}
            {ordered.map((p, i) => {
              const k = KIND[p.kind] || KIND.dom
              const shape = p.kind === 'ideal' ? { borderRadius: 2, transform: 'translate(-50%, 50%) rotate(45deg)' }
                : p.kind === 'nadir' ? { borderRadius: 2 } : null
              return (
                <button key={p.id ?? i} type="button" className="pt" aria-label={`${p.name}: ${p.xText ?? short(p.x)}; ${p.yText ?? short(p.y)}`}
                  onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(p)} onBlur={() => setHover(null)}
                  style={{ left: `${px(p.x)}%`, bottom: `${py(p.y)}%`, width: k.size, height: k.size, background: k.color,
                    boxShadow: `0 0 0 1px ${k.ring}`, cursor: 'default', ...shape }} />
              )
            })}
            {labels.map((l) => (
              <span key={l.text} className="lbl" title={l.text} style={labelPlacement(px(l.x), py(l.y))}>{l.text}</span>
            ))}
            {hover && (
              <span className="tooltip" style={tooltipPlacement(px(hover.x), py(hover.y))}>
                {hover.name} · {hover.xText ?? short(hover.x)} / {hover.yText ?? short(hover.y)}
              </span>
            )}
          </div>
          <div className="x-axis" aria-hidden="true">{tickLabels(X.ticks).map((t, i) => <span key={i}>{t}</span>)}</div>
        </div>
      </div>
      <div className="legend" style={{ marginTop: 8, justifyContent: 'space-between' }}>
        <span>{xLabel}{xHint ? ` (${xHint})` : ''}</span>
        <span>↕ {yLabel}{yHint ? ` (${yHint})` : ''}</span>
      </div>
    </div>
  )
}

export function Legend({ items }) {
  return (
    <div className="legend">
      {items.map((it) => (
        <span key={it.label}><span className={`swatch${it.round ? ' round' : ''}`} style={{ background: it.color }} />{it.label}</span>
      ))}
    </div>
  )
}

// Складена горизонтальна смуга (частки, сума ≤ 1)
export function StackBar({ parts, height = 22, label }) {
  return (
    <div className="stack" style={{ height }} role="img" aria-label={label}>
      {parts.map((p) => (
        <span key={p.label} title={p.label} style={{ width: `${Math.max(p.value, 0) * 100}%`, background: p.color }} />
      ))}
    </div>
  )
}

// Лінійний графік: кілька серій над спільною віссю x; вертикальна мітка vline
export function LineChart({ xs, series, height = 260, vline, xLabel, label }) {
  const all = series.flatMap((s) => s.values).filter(Number.isFinite)
  if (!all.length) return null
  const Y = domain(all)
  const XT = ticks(Math.min(...xs), Math.max(...xs), 5)
  const X = { lo: XT[0], hi: XT[XT.length - 1] }
  const px = (x) => ((x - X.lo) / (X.hi - X.lo || 1)) * 100
  const py = (y) => 100 - ((y - Y.lo) / (Y.hi - Y.lo || 1)) * 100
  return (
    <div>
      <div className="chart">
        <div className="y-axis" aria-hidden="true">{tickLabels(Y.ticks).reverse().map((t, i) => <span key={i}>{t}</span>)}</div>
        <div className="plot-col">
          <div className="plot" role="img" aria-label={label}
            style={{ height, background: `linear-gradient(#EEF1F4 1px, transparent 1px) 0 0 / 100% ${100 / (Y.ticks.length - 1)}%` }}>
            <svg className="lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {vline !== undefined && (
                <line x1={px(vline)} x2={px(vline)} y1="0" y2="100" stroke="#5B6673" strokeDasharray="4 4" strokeWidth="1"
                  vectorEffect="non-scaling-stroke" />
              )}
              {series.map((s, i) => (
                <polyline key={s.name} fill="none" stroke={s.color} strokeWidth={i === 0 ? 3 : 1.8} vectorEffect="non-scaling-stroke"
                  points={s.values.map((v, j) => (Number.isFinite(v) ? `${px(xs[j])},${py(v)}` : '')).filter(Boolean).join(' ')} />
              ))}
            </svg>
          </div>
          <div className="x-axis" aria-hidden="true">
            {tickLabels(XT).map((t, i) => <span key={i}>{t}</span>)}
          </div>
        </div>
      </div>
      {xLabel && <div className="legend" style={{ marginTop: 8 }}><span>{xLabel}</span></div>}
      <div style={{ marginTop: 8 }}><Legend items={series.map((s) => ({ label: s.name, color: s.color }))} /></div>
    </div>
  )
}

// Теплова карта: values[i][j] у [-1; 1] (кореляція) або довільні числа з функцією кольору
export function Heatmap({ rows, cols, values, color, format, label, minCell = 48 }) {
  return (
    <div className="table-wrap" role="img" aria-label={label}>
      <div className="heat" style={{ gridTemplateColumns: `minmax(120px, max-content) repeat(${cols.length}, minmax(${minCell}px, 1fr))` }}>
        <span />
        {cols.map((c) => <span key={c} className="head">{c}</span>)}
        {rows.map((r, i) => (
          <div key={r} style={{ display: 'contents' }}>
            <span className="rowhead">{r}</span>
            {cols.map((c, j) => {
              const v = values[i][j]
              const { bg, fg } = color(v)
              return <span key={c} className="cell" style={{ background: bg, color: fg }}>{format(v)}</span>
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
