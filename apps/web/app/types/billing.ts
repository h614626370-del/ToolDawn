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
}
export interface BillingPage<T> { items: T[]; total: number }
