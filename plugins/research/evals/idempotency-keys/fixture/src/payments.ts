export async function charge(amount: number, currency: string, source: string) {
  const response = await fetch('https://acquirer.example/charge', { method: 'POST', body: JSON.stringify({ amount, currency, source }) })
  if (!response.ok) throw new Error(`acquirer answered ${response.status}`)
  return response.json()
}
