// Клиентская часть сервиса платёжных поручений (без сторонних библиотек).
'use strict';

const $ = (selector) => document.querySelector(selector);
const state = { token: sessionStorage.getItem('token'), user: null, accounts: [], editing: null };
const money = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ROLE = { admin: 'контролёр', operator: 'операционист', auditor: 'аудитор' };
const STATUS = { open: 'открыт', closed: 'закрыт', draft: 'черновик', executed: 'исполнено', rejected: 'отклонено' };
const ACTION = {
  login: 'вход', login_failed: 'неудачный вход', create: 'создание', update: 'изменение',
  delete: 'удаление', execute: 'исполнение', reject: 'отклонение',
};
const ENTITY = { user: 'пользователь', account: 'счёт', payment: 'поручение' };
const ENV = { prod: 'промышленный контур', stage: 'тестовый контур', dev: 'разработка' };

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (response.status === 401 && state.token) {
    logout();
    throw new Error('Сеанс завершён, войдите снова');
  }
  if (response.status === 204) return null;
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? 'Проверьте заполнение полей' : body.detail;
    throw new Error(detail || `Ошибка ${response.status}`);
  }
  return body;
}

function cell(text, className) {
  const td = document.createElement('td');
  td.textContent = text;
  if (className) td.className = className;
  return td;
}

function badge(value) {
  const td = document.createElement('td');
  const span = document.createElement('span');
  span.className = `badge st-${value}`;
  span.textContent = STATUS[value] || value;
  td.append(span);
  return td;
}

function link(text, handler, danger) {
  const button = document.createElement('button');
  button.className = danger ? 'btn-link danger' : 'btn-link';
  button.textContent = text;
  button.addEventListener('click', handler);
  return button;
}

function notify(message) {
  const box = $('#notice');
  box.textContent = message;
  box.classList.toggle('hidden', !message);
  if (message) setTimeout(() => box.classList.add('hidden'), 6000);
}

async function guarded(action) {
  try {
    await action();
  } catch (error) {
    notify(error.message);
  }
}

const canWrite = () => ['admin', 'operator'].includes(state.user.role);
const isAdmin = () => state.user.role === 'admin';

async function loadAccounts() {
  state.accounts = await api('/accounts');
  const body = $('#accounts-body');
  body.replaceChildren();
  for (const account of state.accounts) {
    const row = document.createElement('tr');
    row.append(cell(account.id), cell(account.number, 'mono'), cell(account.owner_name),
      cell(account.currency), cell(money.format(account.balance), 'num'), badge(account.status));
    const actions = cell('', 'actions-cell');
    if (canWrite()) {
      actions.append(link('Изменить', () => openAccountDialog(account)));
      const next = account.status === 'open' ? 'closed' : 'open';
      actions.append(link(next === 'closed' ? 'Закрыть' : 'Открыть', () => guarded(async () => {
        await api(`/accounts/${account.id}`, { method: 'PUT', body: JSON.stringify({ status: next }) });
        await loadAccounts();
      })));
    }
    if (isAdmin()) {
      actions.append(link('Удалить', () => guarded(async () => {
        if (!confirm(`Удалить счёт ${account.number}?`)) return;
        await api(`/accounts/${account.id}`, { method: 'DELETE' });
        await loadAccounts();
      }), true));
    }
    row.append(actions);
    body.append(row);
  }
  const total = state.accounts.filter((item) => item.status === 'open')
    .reduce((sum, item) => sum + Number(item.balance), 0);
  $('#accounts-total').textContent = money.format(total);
}

async function loadPayments() {
  const filter = $('#payment-filter').value;
  const payments = await api(`/payments${filter ? `?status=${filter}` : ''}`);
  const body = $('#payments-body');
  body.replaceChildren();
  for (const payment of payments) {
    const row = document.createElement('tr');
    row.append(cell(payment.id), cell(payment.account_number, 'mono'), cell(payment.beneficiary_name),
      cell(money.format(payment.amount), 'num'), cell(payment.purpose), badge(payment.status),
      cell(payment.created_by));
    const actions = cell('', 'actions-cell');
    if (payment.status === 'draft' && canWrite()) {
      actions.append(link('Изменить', () => openPaymentDialog(payment)));
      if (isAdmin()) {
        actions.append(link('Исполнить', () => paymentAction(payment, 'execute')));
        actions.append(link('Отклонить', () => paymentAction(payment, 'reject')));
      }
      actions.append(link('Удалить', () => guarded(async () => {
        if (!confirm(`Удалить поручение № ${payment.id}?`)) return;
        await api(`/payments/${payment.id}`, { method: 'DELETE' });
        await loadPayments();
      }), true));
    }
    row.append(actions);
    body.append(row);
  }
}

function paymentAction(payment, action) {
  return guarded(async () => {
    await api(`/payments/${payment.id}/${action}`, { method: 'POST' });
    await Promise.all([loadPayments(), loadAccounts()]);
  });
}

async function loadAudit() {
  const events = await api('/audit?limit=100');
  const body = $('#audit-body');
  body.replaceChildren();
  for (const event of events) {
    const row = document.createElement('tr');
    row.append(cell(new Date(event.ts).toLocaleString('ru-RU')), cell(event.username),
      cell(ACTION[event.action] || event.action), cell(ENTITY[event.entity] || event.entity),
      cell(event.entity_id ?? ''), cell(event.details));
    body.append(row);
  }
}

const loaders = { accounts: loadAccounts, payments: loadPayments, audit: loadAudit };

function showTab(name) {
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === name));
  document.querySelectorAll('.panel').forEach((panel) => panel.classList.toggle('hidden', panel.id !== name));
  guarded(loaders[name]);
}

function openDialog(dialog, title, values) {
  const form = dialog.querySelector('form');
  form.reset();
  form.querySelector('.error').classList.add('hidden');
  dialog.querySelector('h3').textContent = title;
  for (const [name, value] of Object.entries(values || {})) {
    if (form.elements[name]) form.elements[name].value = value;
  }
  dialog.showModal();
}

function openAccountDialog(account) {
  state.editing = account || null;
  const dialog = $('#account-dialog');
  openDialog(dialog, account ? `Счёт ${account.number}` : 'Новый счёт', account);
  const form = dialog.querySelector('form');
  form.elements.number.disabled = Boolean(account);
  form.elements.balance.disabled = Boolean(account);
}

function openPaymentDialog(payment) {
  state.editing = payment || null;
  const dialog = $('#payment-dialog');
  const select = dialog.querySelector('select[name=account_id]');
  select.replaceChildren();
  for (const account of state.accounts.filter((item) => item.status === 'open' || payment)) {
    const option = document.createElement('option');
    option.value = account.id;
    option.textContent = `${account.number} · ${account.owner_name}`;
    select.append(option);
  }
  openDialog(dialog, payment ? `Поручение № ${payment.id}` : 'Новое платёжное поручение', payment);
  select.disabled = Boolean(payment);
}

async function submitForm(event, save, reload) {
  event.preventDefault();
  const form = event.target;
  const error = form.querySelector('.error');
  try {
    await save(Object.fromEntries(new FormData(form).entries()));
    form.closest('dialog').close();
    await reload();
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove('hidden');
  }
}

$('#account-form').addEventListener('submit', (event) => submitForm(event, (data) => {
  if (state.editing) {
    return api(`/accounts/${state.editing.id}`, { method: 'PUT', body: JSON.stringify({ owner_name: data.owner_name }) });
  }
  return api('/accounts', { method: 'POST', body: JSON.stringify(data) });
}, loadAccounts));

$('#payment-form').addEventListener('submit', (event) => submitForm(event, (data) => {
  if (state.editing) {
    delete data.account_id;
    return api(`/payments/${state.editing.id}`, { method: 'PUT', body: JSON.stringify(data) });
  }
  return api('/payments', { method: 'POST', body: JSON.stringify({ ...data, account_id: Number(data.account_id) }) });
}, loadPayments));

document.querySelectorAll('[data-close]').forEach((button) => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => showTab(tab.dataset.tab)));
$('#account-add').addEventListener('click', () => openAccountDialog());
$('#payment-add').addEventListener('click', () => guarded(async () => {
  if (!state.accounts.length) await loadAccounts();
  openPaymentDialog();
}));
$('#payment-filter').addEventListener('change', () => guarded(loadPayments));
$('#logout').addEventListener('click', logout);

$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const error = $('#login-error');
  error.classList.add('hidden');
  try {
    const data = Object.fromEntries(new FormData(event.target).entries());
    const result = await api('/auth/login', { method: 'POST', body: JSON.stringify(data) });
    state.token = result.access_token;
    sessionStorage.setItem('token', state.token);
    event.target.reset();
    await start();
  } catch (failure) {
    error.textContent = failure.message;
    error.classList.remove('hidden');
  }
});

function logout() {
  state.token = null;
  state.user = null;
  sessionStorage.removeItem('token');
  $('#app-view').classList.add('hidden');
  $('#userbox').classList.add('hidden');
  $('#login-view').classList.remove('hidden');
}

async function start() {
  state.user = await api('/auth/me');
  $('#user-name').textContent = state.user.full_name;
  $('#user-role').textContent = ROLE[state.user.role] || state.user.role;
  $('#userbox').classList.remove('hidden');
  $('#login-view').classList.add('hidden');
  $('#app-view').classList.remove('hidden');
  $('#tab-audit').classList.toggle('hidden', !['admin', 'auditor'].includes(state.user.role));
  document.querySelectorAll('.write-only').forEach((node) => node.classList.toggle('hidden', !canWrite()));
  showTab('accounts');
}

// В подвале показывается версия и экземпляр серверной части, ответивший на запрос
async function refreshVersion() {
  try {
    const info = await fetch('/api/version').then((response) => response.json());
    $('#backend-info').textContent = `Сервер: версия ${info.version}, экземпляр ${info.instance}`;
    const envBadge = $('#env-badge');
    envBadge.textContent = ENV[info.env] || info.env;
    envBadge.classList.remove('hidden');
  } catch (failure) {
    $('#backend-info').textContent = 'Сервер: недоступен';
  }
}

refreshVersion();
setInterval(refreshVersion, 5000);
if (state.token) start().catch(logout);
