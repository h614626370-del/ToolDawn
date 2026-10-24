export interface CreditPackage {
  id: string
  credits: number
  unit_amount: number
  currency: string
}
export interface CreditEntry {
  id: string
  amount: number
  balance_after: number
  kind: string
  reason: string
  created_at: string
}
export interface PaymentOrder extends CreditPackage {
  package_id: string
  status: 'pending' | 'paid' | 'expired' | 'failed'
  created_at: string
  expires_at: string
  paid_at: string | null
  email?: string
  provider_id?: string | null
  provider_key?: string
  provider_name?: string
  payment_method?: string
}
export interface BillingPage<T> { items: T[]; total: number }
export interface PaymentConfig {
  revision: number
  credit_packages: CreditPackage[]
  stripe_secret_key_set: boolean
  stripe_webhook_secret_set: boolean
}
export interface PaymentStatistics {
  total: number
  statuses: Record<PaymentOrder['status'], number>
  revenue: { currency: string; amount: number; credits: number; orders: number }[]
}
