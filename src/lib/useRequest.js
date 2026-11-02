import { useEffect, useLayoutEffect, useRef, useState } from 'react'

// Запит до API, що повторюється при зміні key (рядок-відбиток вхідних даних).
// Попередній запит скасовується, а частими змінами (повзунки) керує затримка delay.
export function useRequest(fn, key, { delay = 250, enabled = true } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: false })
  const fnRef = useRef(fn)
  useLayoutEffect(() => {
    fnRef.current = fn
  })

  useEffect(() => {
    if (!enabled) return undefined
    const ctrl = new AbortController()
    setState((s) => ({ ...s, loading: true }))
    const t = setTimeout(async () => {
      try {
        const data = await fnRef.current(ctrl.signal)
        if (!ctrl.signal.aborted) setState({ data, error: null, loading: false })
      } catch (e) {
        if (e.name !== 'AbortError' && !ctrl.signal.aborted) setState((s) => ({ ...s, error: e, loading: false }))
      }
    }, delay)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [key, delay, enabled])

  return state
}
