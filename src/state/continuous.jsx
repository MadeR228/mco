import { createContext, useContext, useEffect, useMemo, useReducer } from 'react'

// Стан неперервної задачі: модель (змінні, цілі, обмеження), метод, параметри, побудова фронту.

const KEY = 'mco.continuous.v1'

const initial = {
  exampleId: null,
  title: '',
  description: '',
  variables: [],
  objectives: [],
  constraints: [],
  starts: 8,
  method: 'ideal_point',
  params: { ideal_point: { p: 'inf' } },
  front: { method: 'chebyshev', points: 20, nsga: { pop_size: 100, generations: 100, pc: 0.9, eta_c: 15, eta_m: 20, seed: 1 } },
}

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...initial, ...JSON.parse(raw) } : initial
  } catch {
    return initial
  }
}

function updateList(list, index, patch) {
  return list.map((x, i) => (i === index ? { ...x, ...patch } : x))
}

function reducer(state, a) {
  switch (a.type) {
    case 'loadExample':
      return {
        ...state, exampleId: a.example.id, title: a.example.title, description: a.example.description,
        variables: a.example.variables, objectives: a.example.objectives, constraints: a.example.constraints,
        params: { ideal_point: { p: 'inf' } },
      }
    case 'blank':
      return {
        ...state, exampleId: 'custom', title: 'Власна задача', description: 'Задайте змінні, цілі та обмеження формулами.',
        variables: [{ name: 'x1', lo: 0, hi: 10 }, { name: 'x2', lo: 0, hi: 10 }],
        objectives: [{ name: 'f1', expr: 'x1 + x2', sense: 'max', weight: 0.5 }, { name: 'f2', expr: 'x1^2 + 2*x2', sense: 'min', weight: 0.5 }],
        constraints: [{ expr: 'x1 + 2*x2', op: '≤', rhs: 12 }], params: { ideal_point: { p: 'inf' } },
      }
    case 'edit':
      return { ...state, [a.list]: updateList(state[a.list], a.index, a.patch) }
    case 'add':
      return { ...state, [a.list]: [...state[a.list], a.item] }
    case 'remove':
      return { ...state, [a.list]: state[a.list].filter((_, i) => i !== a.index) }
    case 'setStarts':
      return { ...state, starts: a.starts }
    case 'setMethod':
      return { ...state, method: a.method }
    case 'setParam':
      return { ...state, params: { ...state.params, [a.method]: { ...(state.params[a.method] || {}), [a.name]: a.value } } }
    case 'setFront':
      return { ...state, front: { ...state.front, ...a.patch, nsga: { ...state.front.nsga, ...(a.patch.nsga || {}) } } }
    default:
      return state
  }
}

const Ctx = createContext(null)

export function ContinuousProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, undefined, load)
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state))
    } catch {
      // без сховища стан не зберігається між сесіями
    }
  }, [state])

  const problem = useMemo(() => ({
    variables: state.variables.map((v) => ({ name: String(v.name).trim(), lo: Number(v.lo), hi: Number(v.hi) })),
    objectives: state.objectives.map((o) => ({ ...o, weight: Number(o.weight) || 0 })),
    constraints: state.constraints.map((c) => ({ ...c, rhs: Number(c.rhs) })),
    starts: state.starts,
  }), [state.variables, state.objectives, state.constraints, state.starts])
  const fingerprint = useMemo(() => JSON.stringify(problem), [problem])

  const value = useMemo(() => ({ state, dispatch, problem, fingerprint }), [state, problem, fingerprint])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useContinuous() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useContinuous поза ContinuousProvider')
  return v
}
