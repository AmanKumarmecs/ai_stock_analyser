const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export async function getDefaultSymbols() {
  const res = await fetch(`${API_BASE_URL}/api/default-symbols`)
  if (!res.ok) throw new Error('Could not load default symbols')
  return res.json()
}

export async function analyzeStock(symbol) {
  const safeSymbol = encodeURIComponent(symbol.trim())
  const res = await fetch(`${API_BASE_URL}/api/analyze/${safeSymbol}?period=1y&interval=1d`)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || 'Could not analyze this stock')
  }
  return data
}

export async function trainStock(symbol) {
  const safeSymbol = encodeURIComponent(symbol.trim())
  const res = await fetch(`${API_BASE_URL}/api/train/${safeSymbol}?period=5y&interval=1d`, {
    method: 'POST',
  })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || 'Could not train this stock')
  }
  return data
}

export async function getModelStatus(symbol) {
  const safeSymbol = encodeURIComponent(symbol.trim())
  const res = await fetch(`${API_BASE_URL}/api/model-status/${safeSymbol}`)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || 'Could not load model status')
  }
  return data
}

export async function getLearningStatus(symbol) {
  const safeSymbol = symbol ? encodeURIComponent(symbol.trim()) : ''
  const url = safeSymbol ? `${API_BASE_URL}/api/learning/status/${safeSymbol}` : `${API_BASE_URL}/api/learning/status`
  const res = await fetch(url)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || 'Could not load auto-learning status')
  }
  return data
}

export async function runDailyLearningCycle(symbols = '') {
  const query = symbols ? `?symbols=${encodeURIComponent(symbols)}` : ''
  const res = await fetch(`${API_BASE_URL}/api/learning/daily-cycle${query}`, { method: 'POST' })
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data?.detail || 'Could not run daily learning cycle')
  }
  return data
}
