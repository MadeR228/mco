import { Link } from 'react-router-dom'
import { OkIcon, WarnIcon } from './Icons.jsx'

// Невеликі спільні елементи інтерфейсу

export function Segmented({ label, options, value, onChange, fill = false }) {
  return (
    <div role="group" aria-label={label} className={`segmented${fill ? ' fill' : ''}`}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function ErrorBox({ error, children }) {
  if (!error && !children) return null
  return (
    <div className="alert error" role="alert">
      <WarnIcon />
      <span className="grow">{children || error.message}</span>
    </div>
  )
}

export function Loading({ children = 'Обчислюю…' }) {
  return <div className="loading" role="status"><span className="spinner" aria-hidden="true" />{children}</div>
}

export function OkBox({ title, children, action }) {
  return (
    <div className="alert ok">
      <OkIcon />
      <div className="grow" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <strong style={{ fontSize: 14 }}>{title}</strong>
        {children && <span style={{ fontSize: 12, color: '#2e4b4c' }}>{children}</span>}
      </div>
      {action}
    </div>
  )
}

export function Progress({ value, label }) {
  return (
    <div className="progress" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={Math.round((value || 0) * 100)}>
      <div style={{ width: `${Math.round((value || 0) * 100)}%` }} />
    </div>
  )
}

export function PageHead({ eyebrow, title, children }) {
  return (
    <header className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
      </div>
      {children && <div className="actions">{children}</div>}
    </header>
  )
}

export function NeedData() {
  return (
    <section className="card">
      <h2>Спочатку виберіть дані</h2>
      <p className="note">Завантажте приклад, каталог інтернет-магазину або власний файл на кроці «Дані».</p>
      <Link className="btn primary" to="/discrete/data" style={{ alignSelf: 'flex-start' }}>Перейти до даних</Link>
    </section>
  )
}
