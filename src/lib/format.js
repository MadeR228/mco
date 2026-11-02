// Форматування чисел за українськими правилами: 52 000, 0,738.

const cache = new Map()

function formatter(digits) {
  const key = digits
  if (!cache.has(key)) {
    cache.set(key, new Intl.NumberFormat('uk-UA', { maximumFractionDigits: digits, minimumFractionDigits: 0 }))
  }
  return cache.get(key)
}

export function num(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  if (typeof v !== 'number') return String(v)
  const abs = Math.abs(v)
  const d = abs >= 1000 ? 0 : abs >= 100 ? Math.min(digits, 1) : digits
  return formatter(d).format(v)
}

export function fixed(v, digits = 3) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return new Intl.NumberFormat('uk-UA', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v)
}

export function pct(v, digits = 0) {
  if (v === null || v === undefined) return '—'
  return `${fixed(v * 100, digits)} %`
}

export function ms(v) {
  if (v === null || v === undefined) return '—'
  return v < 10 ? `${fixed(v, 2)} мс` : v < 1000 ? `${fixed(v, 0)} мс` : `${fixed(v / 1000, 1)} с`
}

// Короткі підписи осей: 52 000 → 52k
export function short(v) {
  if (v === null || v === undefined) return ''
  const abs = Math.abs(v)
  if (abs >= 1e6) return `${fixed(v / 1e6, abs >= 1e7 ? 0 : 1)}M`
  if (abs >= 1000) return `${fixed(v / 1000, abs >= 1e4 ? 0 : 1)}k`
  return num(v, abs < 10 ? 2 : 1)
}

export const CRITERIA_COLORS = ['#0F7C7E', '#2F5D9E', '#E0922F', '#8A5A9E', '#5B6673', '#A8C3D3', '#3BB273', '#C04ABC', '#7A4A0E', '#1B998B']

export function colorAt(i) {
  return CRITERIA_COLORS[i % CRITERIA_COLORS.length]
}

// Підписи поділок з точністю, достатньою для їхнього кроку (щоб не було «5,7k, 5,7k»)
export function tickLabels(values) {
  if (values.length < 2) return values.map((v) => short(v))
  const step = Math.abs(values[1] - values[0]) || 1
  const big = Math.max(...values.map(Math.abs)) >= 1000
  const unit = big ? 1000 : 1
  const digits = Math.max(0, Math.min(4, Math.ceil(-Math.log10(step / unit) - 1e-9)))
  return values.map((v) => (big ? `${fixed(v / unit, digits)}k` : fixed(v, digits)))
}

// Рівномірні «круглі» поділки осі
export function ticks(min, max, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1]
  if (min === max) {
    const d = Math.abs(min) || 1
    min -= d / 2
    max += d / 2
  }
  const raw = (max - min) / (count - 1)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const lo = Math.floor(min / step) * step
  const hi = Math.ceil(max / step) * step
  const out = []
  for (let v = lo; v <= hi + step / 2; v += step) out.push(Number(v.toFixed(10)))
  return out
}

export function downloadFile(name, content, type = 'text/plain') {
  const blob = new Blob([content], { type: `${type};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function toCsv(rows, columns) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",;\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return '﻿' + [columns.map(esc).join(','), ...rows.map((r) => columns.map((c) => esc(r[c])).join(','))].join('\n')
}

// Колір для кореляції: синій – збіг, помаранчевий – протилежність
export function corrColor(v) {
  if (v === null || v === undefined) return { bg: '#EDF1F4', fg: '#5B6673' }
  const a = Math.min(Math.abs(v), 1)
  if (v >= 0) {
    const l = Math.round(96 - a * 62)
    return { bg: `hsl(201 55% ${l}%)`, fg: l < 55 ? '#FFFFFF' : '#16202B' }
  }
  const l = Math.round(96 - a * 50)
  return { bg: `hsl(28 80% ${l}%)`, fg: l < 55 ? '#FFFFFF' : '#16202B' }
}
