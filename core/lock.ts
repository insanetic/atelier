/** Serializes async tasks per key: the mod's writes to one study's files must not interleave. */
export class KeyedLock {
  #tails = new Map<string, Promise<unknown>>()

  run<T>(key: string, task: () => Promise<T>): Promise<T> {
    const previous = this.#tails.get(key) ?? Promise.resolve()
    const current = previous.then(task, task)
    this.#tails.set(key, current.catch(() => undefined))
    return current
  }
}
