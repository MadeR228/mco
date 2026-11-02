import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api.js'

// Реєстр методів з бекенду (GET /api/methods) – завантажується один раз
const Ctx = createContext({ meta: null, error: null })

export function MetaProvider({ children }) {
  const [state, setState] = useState({ meta: null, error: null })
  useEffect(() => {
    api.methods().then((meta) => setState({ meta, error: null })).catch((error) => setState({ meta: null, error }))
  }, [])
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useMeta() {
  return useContext(Ctx)
}
