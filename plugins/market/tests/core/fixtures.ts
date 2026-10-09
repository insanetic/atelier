import { toYaml } from '../../../research/core/index.ts'
import type { FakeIo } from '../../../research/tests/core/fake-io.ts'
import { CFG, TODAY, seedStudy } from '../../../research/tests/core/fixtures.ts'
import { marketFiles } from '../../core/paths.ts'
import type { Registry, Taxonomy } from '../../core/types.ts'

export { CFG, TODAY }

export const TAXONOMY: Taxonomy = {
  categories: {
    'subscription-billing': 'Recurring plans, invoices and the subscription lifecycle',
    'usage-billing': 'Billing on metered consumption',
    entitlements: 'Feature access and limits decoupled from billing',
  },
  capabilities: {
    public_api: 'A documented public API customers integrate against',
    self_hosted: 'Customers can run it on their own infrastructure',
  },
}

export const REGISTRY: Registry = {
  lago: {
    domains: ['getlago.com'],
    categories: ['usage-billing', 'subscription-billing'],
    source_model: 'open_source',
    status: 'active',
    stance: { tier: 1, overlap: { 'usage-billing': 'direct' }, reviewed: '2026-10-01' },
  },
  stripe: {
    domains: ['stripe.com'],
    categories: ['subscription-billing'],
    stance: { tier: 1, overlap: { 'subscription-billing': 'direct' }, reviewed: '2026-10-01' },
  },
}

/** research's tax study and references (lago, stripe, subneo as ours), plus the market files. */
export function seedMarket(io: FakeIo): void {
  seedStudy(io)
  io.files.set(marketFiles.taxonomy(CFG), toYaml(TAXONOMY))
  io.files.set(marketFiles.registry(CFG), toYaml(REGISTRY))
}
