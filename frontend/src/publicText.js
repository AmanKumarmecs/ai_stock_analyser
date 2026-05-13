export function cleanPublicText(text) {
  if (!text) return text
  return String(text)
    .replace(/NIFTY\s*50/gi, 'overall market')
    .replace(/NIFTY/gi, 'overall market')
    .replace(/DMI\s*\/\s*ADX/gi, 'trend strength')
    .replace(/DMI-ADX/gi, 'trend strength')
    .replace(/DMI/gi, 'trend direction')
    .replace(/ADX/gi, 'trend strength')
    .replace(/SMA/gi, 'moving average')
    .replace(/MACD/gi, 'momentum')
    .replace(/RSI/gi, 'momentum score')
    .replace(/Neon DB/gi, 'learning history')
    .replace(/GitHub Actions/gi, 'scheduled learning')
    .replace(/Kaggle/gi, 'offline training')
    .replace(/trained-model features/gi, 'analysis factors')
    .replace(/free-tier/gi, 'limited')
    .replace(/DB/gi, 'records')
}
