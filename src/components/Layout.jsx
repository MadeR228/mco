import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useContinuous } from '../state/continuous.jsx'
import { useProblem } from '../state/problem.jsx'
import { BookIcon, CurveIcon, ScaleIcon, TableIcon } from './Icons.jsx'

function DatasetBox() {
  const { state, used } = useProblem()
  if (!state.table) {
    return (
      <div className="side-box">
        <span className="side-label">Набір даних</span>
        <span style={{ fontSize: 14, color: 'var(--on-dark-soft)' }}>ще не вибрано</span>
        <Link to="/discrete/data">Вибрати дані</Link>
      </div>
    )
  }
  return (
    <div className="side-box">
      <span className="side-label">Набір даних</span>
      <span style={{ fontSize: 15, fontWeight: 600 }}>{state.table.title}</span>
      <span style={{ fontSize: 13, color: 'var(--on-dark-soft)' }}>
        {state.table.rows} альтернатив · {used.length} критеріїв
      </span>
      <Link to="/discrete/data">Змінити джерело</Link>
    </div>
  )
}

function ExamplesBox() {
  const { state } = useContinuous()
  return (
    <div className="side-box">
      <span className="side-label">Задача</span>
      <span style={{ fontSize: 15, fontWeight: 600 }}>{state.title || 'не вибрано'}</span>
      <span style={{ fontSize: 13, color: 'var(--on-dark-soft)' }}>
        {state.variables.length} змінні · {state.objectives.length} цілі · {state.constraints.length} обмеження
      </span>
    </div>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  const discrete = pathname.startsWith('/discrete')
  return (
    <div className="app">
      <aside className="sidebar">
        <Link to="/" className="brand" aria-label="MCO – на головну">
          <span className="brand-mark"><ScaleIcon /></span>
          <span style={{ display: 'flex', flexDirection: 'column' }}>
            <span className="brand-name">MCO</span>
            <span className="brand-sub">багатокритеріальна оптимізація</span>
          </span>
        </Link>
        <nav aria-label="Режим роботи" className="side-nav">
          <span className="side-label">Режим</span>
          <NavLink to="/discrete/data" className={() => `side-link${discrete ? ' active' : ''}`}
            aria-current={discrete ? 'page' : undefined}>
            <TableIcon />Дискретний вибір
          </NavLink>
          <NavLink to="/continuous" className={({ isActive }) => `side-link${isActive ? ' active' : ''}`}>
            <CurveIcon />Неперервна задача
          </NavLink>
          <NavLink to="/help" className={({ isActive }) => `side-link${isActive ? ' active' : ''}`}>
            <BookIcon />Довідка
          </NavLink>
        </nav>
        {discrete && <DatasetBox />}
        {pathname.startsWith('/continuous') && <ExamplesBox />}
        <span className="side-foot">ЛР 12–13 · v1.0</span>
      </aside>
      <main className="main" id="main">
        <Outlet />
      </main>
    </div>
  )
}
