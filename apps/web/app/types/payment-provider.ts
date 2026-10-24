export type ProviderKind = 'easypay' | 'alipay' | 'wxpay' | 'stripe' | 'airwallex'
export interface ProviderField { key: string; label: string; secret: boolean; multiline: boolean; options: string[] | null; default: string; optional: boolean }
export interface ProviderType { kind: ProviderKind; name: string; methods: string[]; currencies: string[]; fields: ProviderField[]; events: string[] }
export interface PaymentProvider {
  id: string; name: string; kind: ProviderKind; enabled: boolean; sort_order: number; revision: number
  methods: string[]; config: Record<string, string>; secrets_set: Record<string, boolean>; webhook_url: string; config_locked: boolean
}
export interface PaymentMethod { id: string | null; name: string; kind: ProviderKind; methods: string[]; currencies: string[] }
export interface CheckoutResult { order_id: string; url: string; qr_code: string | null; expires_at: string | null }
