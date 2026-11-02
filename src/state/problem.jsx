import { createContext, useCallback, useContext, useEffect, useMemo, useReducer } from 'react'

// Стан дискретної задачі: таблиця альтернатив, критерії, обмеження, метод і його параметри.
// Зберігається в localStorage (лише як зручність: без нього застосунок працює так само).

const KEY = 'mco.discrete.v1'
const MAX_STORED_ROWS = 5000

const initial = {
  table: null,          // {title, columns, numeric_columns, name_column, records, rows, note, source}
  criteria: [],         // [{name, use, sense, weight}]
  constraints: [],      // [{column, op, value}]
  missing: 'drop',      // 'drop' | 'median'
  method: 'weighted_sum',
  params: {},           // {[method]: {...}}
  weightMode: 'manual',
  ahp: {},              // {'i|j': значення шкали Сааті}
}

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return initial
    return { ...initial, ...JSON.parse(raw) }
  } catch {
    return initial
  }
}

function reducer(state, action) {
  switch (action.type) {
    case 'setTable': {
      const t = action.table
      return {
        ...state,
        table: t,
        criteria: (t.suggested_criteria || []).map((c) => ({ ...c })),
        constraints: (t.suggested_constraints || []).map((c) => ({ ...c })),
        weightMode: 'manual',
        ahp: {},
        params: {},
      }
    }
    case 'updateCriterion':
      return { ...state, criteria: state.criteria.map((c) => (c.name === action.name ? { ...c, ...action.patch } : c)) }
    case 'setWeights':
      return { ...state, criteria: state.criteria.map((c) => (c.name in action.weights ? { ...c, weight: action.weights[c.name] } : c)) }
    case 'setWeightMode':
      return { ...state, weightMode: action.mode }
    case 'setAhp':
      return { ...state, ahp: { ...state.ahp, [action.key]: action.value } }
    case 'addConstraint':
      return { ...state, constraints: [...state.constraints, action.constraint] }
    case 'removeConstraint':
      return { ...state, constraints: state.constraints.filter((_, i) => i !== action.index) }
    case 'setMissing':
      return { ...state, missing: action.missing }
    case 'setMethod':
      return { ...state, method: action.method }
    case 'setParam':
      return { ...state, params: { ...state.params, [action.method]: { ...(state.params[action.method] || {}), [action.name]: action.value } } }
    case 'resetParams':
      return { ...state, params: { ...state.params, [action.method]: {} } }
    default:
      return state
  }
}

const Ctx = createContext(null)

export function ProblemProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, undefined, load)

  useEffect(() => {
    try {
      const stored = state.table && state.table.records.length > MAX_STORED_ROWS ? { ...state, table: null } : state
      localStorage.setItem(KEY, JSON.stringify(stored))
    } catch {
      // сховище недоступне або переповнене – стан просто не зберігається між сесіями
    }
  }, [state])

  const used = useMemo(() => state.criteria.filter((c) => c.use), [state.criteria])

  // Тіло запиту до API (постановка задачі)
  const problem = useMemo(() => {
    if (!state.table) return null
    return {
      records: state.table.records,
      name_column: state.table.name_column,
      criteria: used.map(({ name, sense, weight }) => ({ name, sense, weight })),
      constraints: state.constraints,
      missing: state.missing,
    }
  }, [state.table, used, state.constraints, state.missing])

  // Відбиток постановки без самих записів – для перезапуску запитів при зміні
  const fingerprint = useMemo(() => JSON.stringify({
    t: state.table ? [state.table.title, state.table.rows, state.table.source] : null,
    c: used.map((c) => [c.name, c.sense, c.weight]),
    k: state.constraints, m: state.missing,
  }), [state.table, used, state.constraints, state.missing])

  const gaps = useMemo(() => {
    if (!state.table) return { rows: 0, columns: [] }
    const cols = used.map((c) => c.name)
    let rows = 0
    const bad = new Set()
    for (const r of state.table.records) {
      let miss = false
      for (const c of cols) {
        if (r[c] === null || r[c] === undefined || r[c] === '') {
          miss = true
          bad.add(c)
        }
      }
      if (miss) rows += 1
    }
    return { rows, columns: [...bad] }
  }, [state.table, used])

  const setParam = useCallback((method, name, value) => dispatch({ type: 'setParam', method, name, value }), [])

  const value = useMemo(() => ({ state, dispatch, used, problem, fingerprint, gaps, setParam }),
    [state, used, problem, fingerprint, gaps, setParam])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useProblem() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useProblem поза ProblemProvider')
  return v
}
