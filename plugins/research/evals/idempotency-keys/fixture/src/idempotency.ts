import type { Request, Response, NextFunction } from 'express'

type Saved = { status: number; body: unknown }

// Responses by Idempotency-Key, so a retried POST returns the first answer.
const saved = new Map<string, Saved>()

export function idempotency(req: Request, res: Response, next: NextFunction) {
  const key = req.header('Idempotency-Key')
  if (!key) return next()
  const hit = saved.get(key)
  if (hit) return res.status(hit.status).json(hit.body)
  const json = res.json.bind(res)
  res.json = (body: unknown) => {
    saved.set(key, { status: res.statusCode, body })
    return json(body)
  }
  next()
}
