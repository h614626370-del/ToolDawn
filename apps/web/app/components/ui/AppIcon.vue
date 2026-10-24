<script setup lang="ts">
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, Bookmark, Check, ChevronDown,
  CodeXml, Coffee, Compass, Gift, Grid2X2, Heart, Image, Layers,
  LoaderCircle, RefreshCw, Scissors, Search, Sparkles, Sun, Text,
  Wrench, X, Minimize2, PenLine, CircleAlert, Mail, LogIn, LogOut, UserRound,
  Plus, Save, ShieldCheck, Ban, Globe2, Wallet, CreditCard, ReceiptText,
  Copy, Download, Trash2,
  Activity, ChartNoAxesCombined, Settings2, KeyRound, LifeBuoy, History, Send, Eye,
} from '@lucide/vue'

const props = withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
const icons: Record<string, typeof Search> = {
  search: Search, grid: Grid2X2, image: Image, text: Text, coffee: Coffee,
  wrench: Wrench, bookmark: Bookmark, heart: Heart, sun: Sun, compass: Compass,
  arrow: ArrowRight, back: ArrowLeft, external: ArrowUpRight, down: ArrowDown,
  chevron: ChevronDown, close: X, sparkles: Sparkles, gift: Gift, refresh: RefreshCw,
  compress: Minimize2, pen: PenLine, scissors: Scissors, layers: Layers,
  code: CodeXml, loader: LoaderCircle, check: Check, alert: CircleAlert,
  mail: Mail, login: LogIn, logout: LogOut, user: UserRound,
  plus: Plus, save: Save, shield: ShieldCheck, ban: Ban,
  globe: Globe2, wallet: Wallet, card: CreditCard, receipt: ReceiptText,
  copy: Copy, download: Download, trash: Trash2,
  activity: Activity, chart: ChartNoAxesCombined, settings: Settings2, key: KeyRound,
  support: LifeBuoy, history: History, send: Send, eye: Eye,
}
const icon = computed(() => icons[props.name] || Compass)
</script>

<template>
  <component :is="icon" :size="size" :stroke-width="1.8" aria-hidden="true" />
</template>
