const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

async function readResponse(res, fallbackMessage) {
  let data = null
  try {
    data = await res.json()
  } catch {
    data = null
  }
  if (!res.ok) {
    throw new Error(fallbackMessage)
  }
  return data
}

export async function getDefaultSymbols() {
  const res = await fetch(`${API_BASE_URL}/api/default-symbols`)
  return readResponse(res, 'Could not load stock list')
}

export async function analyzeStock(symbol) {
  const safeSymbol = encodeURIComponent(symbol.trim())
  const res = await fetch(`${API_BASE_URL}/api/analyze/${safeSymbol}?period=1y&interval=1d`)
  return readResponse(res, 'Market analysis could not be loaded right now')
}
