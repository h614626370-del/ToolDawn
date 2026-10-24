export function useBillingFormat() {
  const { locale, t } = useI18n()
  const money = (amount: number, currency: string) => new Intl.NumberFormat(locale.value, {
    style: 'currency', currency: currency.toUpperCase(),
  }).format(amount / 100)
  const date = (value: string) => new Intl.DateTimeFormat(locale.value, {
    dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(value))
  const status = (value: string) => t({
    pending: '待支付', paid: '已支付', expired: '已过期', failed: '支付失败',
  }[value] || value)
  const kind = (value: string) => t({
    purchase: '充值入账', adjustment: '管理调整', usage: '工具消费',
    tool_usage: '工具消费', tool_refund: '工具退分',
  }[value] || value)
  return { money, date, status, kind }
}
