// Клієнт MCO API (FastAPI-бекенд у теці backend/).

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

function detailText(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // помилки валідації pydantic: [{loc, msg}]
    return detail.map((d) => `${(d.loc || []).filter((x) => x !== 'body').join(' → ')}: ${d.msg}`).join('; ')
  }
  return 'Невідома помилка сервера'
}

async function request(path, { method = 'GET', body, form, signal } = {}) {
  let resp
  try {
    resp = await fetch(path, {
      method,
      signal,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: form ?? (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError('Немає зв’язку з сервером. Запустіть бекенд: uvicorn api.main:app --port 8000', 0)
  }
  const text = await resp.text()
  let data
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!resp.ok) throw new ApiError(detailText(data?.detail) || `Помилка ${resp.status}`, resp.status)
  return data
}

export const api = {
  methods: () => request('/api/methods'),
  datasets: () => request('/api/datasets'),
  dataset: (id) => request(`/api/datasets/${encodeURIComponent(id)}`),
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/upload', { method: 'POST', form })
  },
  shops: () => request('/api/shops'),
  loadShop: (shop, body) => request(`/api/jobs/shops/${encodeURIComponent(shop)}`, { method: 'POST', body }),
  job: (id, signal) => request(`/api/jobs/${encodeURIComponent(id)}`, { signal }),
  solve: (body, signal) => request('/api/discrete/solve', { method: 'POST', body, signal }),
  feasibility: (body, signal) => request('/api/discrete/feasibility', { method: 'POST', body, signal }),
  compare: (body, signal) => request('/api/discrete/compare', { method: 'POST', body, signal }),
  sensitivity: (body, signal) => request('/api/discrete/sensitivity', { method: 'POST', body, signal }),
  montecarlo: (body, signal) => request('/api/discrete/montecarlo', { method: 'POST', body, signal }),
  weights: (method, body) => request(`/api/weights/${method}`, { method: 'POST', body }),
  examples: () => request('/api/continuous/examples'),
  example: (id) => request(`/api/continuous/examples/${encodeURIComponent(id)}`),
  analyze: (body, signal) => request('/api/continuous/analyze', { method: 'POST', body, signal }),
  contSolve: (body, signal) => request('/api/continuous/solve', { method: 'POST', body, signal }),
  front: (body, signal) => request('/api/continuous/front', { method: 'POST', body, signal }),
  frontJob: (body) => request('/api/jobs/front', { method: 'POST', body }),
  doc: (name) => request(`/api/docs/${encodeURIComponent(name)}`),
}

// Опитування фонової задачі до завершення; onProgress(job) отримує проміжний стан.
export async function waitJob(job, { onProgress, signal, interval = 400 } = {}) {
  let current = job
  while (current.status === 'queued' || current.status === 'running') {
    onProgress?.(current)
    await new Promise((resolve, reject) => {
      const t = setTimeout(resolve, interval)
      signal?.addEventListener('abort', () => {
        clearTimeout(t)
        reject(new DOMException('Скасовано', 'AbortError'))
      })
    })
    current = await api.job(current.id, signal)
  }
  onProgress?.(current)
  if (current.status === 'error') throw new ApiError(current.error, 422)
  return current.result
}
