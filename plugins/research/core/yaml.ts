import { parse, parseDocument, stringify } from 'yaml'

export function parseYaml(text: string): unknown {
  return parse(text) ?? null
}

export function toYaml(value: unknown): string {
  return stringify(value, { lineWidth: 0 })
}

/** Sets top-level keys in a hand-edited YAML mapping, keeping its comments and layout. */
export function setInYaml(text: string, values: Record<string, unknown>): string {
  const doc = parseDocument(text)
  for (const [key, value] of Object.entries(values)) doc.set(key, doc.createNode(value))
  return doc.toString({ lineWidth: 0 })
}

/** Appends one item to a hand-edited YAML list, keeping its comments and layout. */
export function appendToYamlList(text: string, item: unknown): string {
  const doc = parseDocument(text)
  if (doc.contents === null) return stringify([item], { lineWidth: 0 })
  doc.add(doc.createNode(item))
  return doc.toString({ lineWidth: 0 })
}
