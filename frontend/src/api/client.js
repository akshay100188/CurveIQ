const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail?.detail || err.detail || res.statusText)
  }
  return res.json()
}

export const get  = (path)         => request(path)
export const post = (path, body)   => request(path, { method: 'POST', body: JSON.stringify(body) })
