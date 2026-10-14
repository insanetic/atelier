import express from 'express'
import { idempotency } from './idempotency'
import { charge } from './payments'

const app = express()
app.use(express.json())
app.post('/v1/charges', idempotency, async (req, res) => {
  try {
    res.status(201).json(await charge(req.body.amount, req.body.currency, req.body.source))
  } catch (problem) {
    res.status(502).json({ error: 'card network unavailable' })
  }
})
app.listen(3000)
