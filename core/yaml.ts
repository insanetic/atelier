import { parse, stringify } from 'yaml'

export function parseYaml(text: string): unknown {
  return parse(text) ?? null
}

export function toYaml(value: unknown): string {
  return stringify(value, { lineWidth: 0 })
}
