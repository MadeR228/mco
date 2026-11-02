import { Link } from 'react-router-dom'

const STEPS = [
  { key: 'data', label: 'Дані', to: '/discrete/data' },
  { key: 'criteria', label: 'Критерії й ваги', to: '/discrete/criteria' },
  { key: 'limits', label: 'Обмеження', to: '/discrete/limits' },
  { key: 'solution', label: 'Розв’язок', to: '/discrete/solution' },
  { key: 'compare', label: 'Порівняння', to: '/discrete/compare' },
  { key: 'sensitivity', label: 'Чутливість', to: '/discrete/sensitivity' },
]

// Кроки дискретного вибору; кроки до поточного позначено як виконані
export default function Stepper({ current }) {
  const at = STEPS.findIndex((s) => s.key === current)
  return (
    <nav aria-label="Кроки" className="stepper">
      <ol>
        {STEPS.map((s, i) => {
          const cls = i === at ? 'active' : i < at ? 'done' : ''
          return (
            <li key={s.key}>
              <Link to={s.to} className={`step ${cls}`} aria-current={i === at ? 'step' : undefined}>
                <span className="dot">{i < at ? '✓' : i + 1}</span>{s.label}
              </Link>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
