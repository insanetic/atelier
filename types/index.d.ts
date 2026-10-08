// Self-contained by rule: the contract may not import. register.tsx narrows
// matrix and findings to core's Matrix and Finding when it reads them.
export type ActiveStudy = { topic: string; matrix: unknown; findings: unknown[] }

declare module 'claude-code' {
  interface PluginState {
    'research-kit': { active: ActiveStudy | null; selected: string | null }
  }
}
