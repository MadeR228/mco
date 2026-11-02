// Параметри методу з форми → тіло запиту: рядкові значення порогів/цілей стають числами,
// порожні й некоректні відкидаються, значення null не надсилаються.
export function cleanParams(params) {
  const out = {}
  for (const [k, v] of Object.entries(params || {})) {
    if (v === null || v === undefined) continue
    if (typeof v === 'object' && !Array.isArray(v)) {
      const dict = {}
      for (const [name, raw] of Object.entries(v)) {
        const n = Number(String(raw).replace(',', '.').trim())
        if (String(raw).trim() !== '' && Number.isFinite(n)) dict[name] = n
      }
      if (Object.keys(dict).length) out[k] = dict
    } else {
      out[k] = v
    }
  }
  return out
}
