<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const items = ref([])
const detail = ref(null)
const err = ref('')
const open = async (id) => {
  err.value = ''
  detail.value = null
  try { detail.value = await getJSON(`/api/history/${id}`) }
  catch (e) { err.value = e.message }
}
onMounted(async () => { items.value = (await getJSON('/api/history')).items })
</script>
<template><div class="page"><h1>试算记录</h1>
<table>
  <tr><th>#</th><th>类型</th><th>贷款</th><th>时间</th><th></th></tr>
  <tr v-for="h in items" :key="h.id">
    <td>#{{ h.id }}</td><td>{{ h.kind }}</td><td>{{ h.loan_id ?? '—' }}</td><td>{{ h.created_at }}</td>
    <td><button @click="open(h.id)">打开</button></td>
  </tr>
</table>
<p v-if="err" class="err">{{ err }}</p>
<div v-if="detail" class="detail">
  <h2>条目 #{{ detail.id }}</h2>
  <p>月供 {{ detail.result.monthly_payment }} · 利息合计 {{ detail.result.total_interest }}</p>
  <h3>利率切换</h3>
  <table v-if="detail.result.rate_switches && detail.result.rate_switches.length">
    <tr><th>切换期</th><th>切换前利率%</th><th>切换后利率%</th><th>切换前月供</th><th>切换后月供</th><th>切换前利息合计</th><th>切换后利息合计</th></tr>
    <tr v-for="s in detail.result.rate_switches" :key="s.switch_period">
      <td>第 {{ s.switch_period }} 期</td>
      <td>{{ s.rate_before }}</td>
      <td>{{ s.rate_after }}</td>
      <td>{{ s.payment_before }}</td>
      <td>{{ s.payment_after }}</td>
      <td>{{ s.interest_before }}</td>
      <td>{{ s.interest_after }}</td>
    </tr>
  </table>
  <p v-else>单利率表，无切换标注。</p>
</div>
</div></template>
<style scoped>
.detail { margin-top:1rem; }
.err { color:#a00; }
</style>
