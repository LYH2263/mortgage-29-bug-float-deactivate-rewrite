<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON, putJSON } from '../api'

const loans = ref([])
const loanId = ref(null)
const events = ref([])
const err = ref('')
const form = ref({ id: null, effective_period: 13, new_annual_rate: 4.2, note: '' })

const loadEvents = async () => {
  err.value = ''
  if (!loanId.value) { events.value = []; return }
  try { events.value = (await getJSON(`/api/loans/${loanId.value}/rate-events`)).items }
  catch (e) { err.value = e.message }
}
const pickLoan = async () => { resetForm(); await loadEvents() }
const resetForm = () => { form.value = { id: null, effective_period: 13, new_annual_rate: 4.2, note: '' } }

const submit = async () => {
  err.value = ''
  const body = {
    effective_period: Number(form.value.effective_period),
    new_annual_rate: Number(form.value.new_annual_rate),
    note: form.value.note || '',
  }
  try {
    if (form.value.id) {
      await putJSON(`/api/rate-events/${form.value.id}`, body)
    } else {
      await postJSON(`/api/loans/${loanId.value}/rate-events`, body)
    }
    resetForm()
    await loadEvents()
  } catch (e) {
    let msg = e.message
    try { msg = JSON.parse(e.message).detail || msg } catch { /* keep raw */ }
    err.value = msg
  }
}
const edit = (ev) => {
  form.value = { id: ev.id, effective_period: ev.effective_period, new_annual_rate: ev.new_annual_rate, note: ev.note || '' }
  err.value = ''
}
const disable = async (ev) => {
  err.value = ''
  try {
    await postJSON(`/api/rate-events/${ev.id}/disable`, {})
    if (form.value.id === ev.id) resetForm()
    await loadEvents()
  } catch (e) { err.value = e.message }
}

onMounted(async () => {
  loans.value = (await getJSON('/api/loans')).items
  if (loans.value.length) { loanId.value = loans.value[0].id; await loadEvents() }
})
</script>
<template><div class="page"><h1>利率浮动事件</h1>
<label>贷款
  <select v-model.number="loanId" @change="pickLoan">
    <option v-for="l in loans" :key="l.id" :value="l.id">{{ l.name }}（{{ l.months }}期 · 原利率 {{ l.annual_rate }}%）</option>
  </select>
</label>

<table v-if="events.length">
  <tr><th>#</th><th>生效期</th><th>新年利率%</th><th>状态</th><th>备注</th><th>操作</th></tr>
  <tr v-for="ev in events" :key="ev.id">
    <td>{{ ev.id }}</td>
    <td>第 {{ ev.effective_period }} 期</td>
    <td>{{ ev.new_annual_rate }}</td>
    <td>{{ ev.enabled ? '启用' : '已停用' }}</td>
    <td>{{ ev.note }}</td>
    <td>
      <button v-if="ev.enabled" @click="edit(ev)">编辑</button>
      <button v-if="ev.enabled" @click="disable(ev)">停用</button>
    </td>
  </tr>
</table>
<p v-else>暂无浮动事件，测算按原年利率等额本息。</p>

<h2>{{ form.id ? `编辑事件 #${form.id}` : '新建浮动事件' }}</h2>
<label>生效期序号 <input v-model.number="form.effective_period" type="number" min="2" /></label>
<label>新年利率% <input v-model.number="form.new_annual_rate" type="number" min="0" step="0.01" /></label>
<label>备注 <input v-model="form.note" /></label>
<button @click="submit">{{ form.id ? '保存修改' : '创建' }}</button>
<button v-if="form.id" @click="resetForm">取消编辑</button>
<p v-if="err" class="err">{{ err }}</p>
<p class="hint">生效期须大于 1 且不超过贷款总期数；同一贷款两条启用事件生效期相同将被拒绝。</p>
</div></template>
<style scoped>
label { display:block; margin:0.4rem 0; }
button { margin:0.3rem 0.4rem 0.3rem 0; }
.err { color:#a00; }
.hint { color:#666; font-size:0.85rem; }
</style>
