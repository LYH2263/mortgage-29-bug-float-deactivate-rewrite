<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
const loans = ref([])
const loanId = ref('')
const principal = ref(800000)
const annual_rate = ref(4.2)
const months = ref(360)
const out = ref(null)
const err = ref('')

const pickLoan = () => {
  const l = loans.value.find(x => x.id === Number(loanId.value))
  if (l) { principal.value = l.principal; annual_rate.value = l.annual_rate; months.value = l.months }
  out.value = null
}
const run = async () => {
  err.value = ''
  try {
    const body = {
      principal: principal.value, annual_rate: annual_rate.value, months: months.value,
      persist: true,
    }
    if (loanId.value !== '') body.loan_id = Number(loanId.value)
    out.value = await postJSON('/api/schedule', body)
  } catch (e) { err.value = e.message }
}
onMounted(async () => {
  loans.value = (await getJSON('/api/loans')).items
  if (loans.value.length) { loanId.value = loans.value[0].id; pickLoan() }
})
</script>
<template><div class="page"><h1>等额本息试算</h1>
<label>贷款
  <select v-model="loanId" @change="pickLoan">
    <option value="">自定义（不挂贷款）</option>
    <option v-for="l in loans" :key="l.id" :value="l.id">{{ l.name }}（{{ l.months }}期 · {{ l.annual_rate }}%）</option>
  </select>
</label>
<label>本金 <input v-model.number="principal" /></label>
<label>年利率% <input v-model.number="annual_rate" /></label>
<label>月数 <input v-model.number="months" /></label>
<button @click="run">计算</button>
<p v-if="err" class="err">{{ err }}</p>
<div v-if="out">
  <p>月供 {{ out.monthly_payment }} · 利息合计 {{ out.total_interest }}</p>
  <h2>利率切换</h2>
  <table v-if="out.rate_switches && out.rate_switches.length">
    <tr><th>切换期</th><th>切换前利率%</th><th>切换后利率%</th><th>切换前月供</th><th>切换后月供</th><th>切换前利息合计</th><th>切换后利息合计</th></tr>
    <tr v-for="s in out.rate_switches" :key="s.switch_period">
      <td>第 {{ s.switch_period }} 期</td>
      <td>{{ s.rate_before }}</td>
      <td>{{ s.rate_after }}</td>
      <td>{{ s.payment_before }}</td>
      <td>{{ s.payment_after }}</td>
      <td>{{ s.interest_before }}</td>
      <td>{{ s.interest_after }}</td>
    </tr>
  </table>
  <p v-else>无启用浮动事件，全程按 {{ annual_rate }}% 等额本息。</p>
</div>
</div></template>
<style scoped>
label { display:block; margin:0.4rem 0; }
.err { color:#a00; }
h2 { margin-top:1rem; }
</style>
