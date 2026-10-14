// Self-contained by rule: the contract may not import.
export type ActiveTopic = string | null

declare module 'claude-code' {
  interface PluginState {
    'research': { active: ActiveTopic }
  }
}
