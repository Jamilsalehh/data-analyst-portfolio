/**
 * Agent-Network Collections Pipeline (Google Apps Script)
 *
 * RAW_PAYMENTS + RAW_POLICY_SALES  (pasted exports, text)
 *        │  parse, clean, validate, de-duplicate, link
 *        ▼
 * FCT_PAYMENTS · FCT_POLICY_SALES  (one clean row per payment / policy sale)
 *        │  aggregate
 *        ▼
 * MART_DAILY · DIM_AGENT           (what Looker Studio reads)
 *
 * Every run writes one row to LOAD_LOG, and every row that fails a check goes
 * to DQ_LOG with the reason. Re-loading a month REPLACES those days instead of
 * duplicating them, so the load is safe to run twice.
 */

const SCRIPT_VERSION = '1.3.0';
const PLACEHOLDER_POLICY = ['0', 'N/A', 'NA', '-', '123', ''];

const SHEETS = {
  rawPay: 'RAW_PAYMENTS', rawSales: 'RAW_POLICY_SALES', config: 'CONFIG', aliases: 'DIM_INSURER',
  fctPay: 'FCT_PAYMENTS', fctSales: 'FCT_POLICY_SALES', mart: 'MART_DAILY', dimAgent: 'DIM_AGENT',
  dq: 'DQ_LOG', log: 'LOAD_LOG',
};

const FCT_PAY_HEADERS = ['txn_key', 'txn_ts', 'txn_date', 'weekday', 'txn_hour', 'agent_code', 'agent_name',
  'agent_network', 'amount_lbp', 'amount_usd', 'fee_band', 'insurer', 'policy_no', 'inception_date', 'expiry_date',
  'policy_term_days', 'insurance_timing', 'bought_here', 'bought_here_same_day', 'dq_flags', 'dq_status', 'load_id'];
const FCT_SALES_HEADERS = ['sale_id', 'sale_ts', 'sale_date', 'insurer', 'agent_name', 'policy_no', 'policy_type',
  'premium_usd', 'load_id'];
const MART_HEADERS = ['txn_date', 'weekday', 'agent_network', 'insurer', 'payments', 'amount_usd', 'flagged_payments',
  'bought_here_same_day', 'policies_sold', 'premium_usd'];
const DIM_AGENT_HEADERS = ['agent_code', 'agent_name', 'agent_network', 'first_txn_date', 'last_txn_date',
  'days_since_last_txn', 'activity_status', 'active_days', 'payments', 'amount_usd', 'payments_last_30d',
  'amount_usd_last_30d', 'rank_last_30d', 'tier_last_30d', 'same_day_policy_rate'];
const DQ_HEADERS = ['load_id', 'txn_key', 'txn_date', 'agent_name', 'dq_flags', 'policy_no', 'insurer_raw',
  'inception_raw', 'expiry_raw'];
const LOG_HEADERS = ['load_id', 'run_at', 'run_by', 'script_version', 'raw_payment_rows', 'duplicates_skipped',
  'unparseable_rows', 'payments_loaded', 'payments_flagged', 'sales_loaded', 'days_replaced', 'date_from', 'date_to',
  'total_usd', 'warnings', 'duration_s'];

/* ------------------------------------------------------------------ menu */
function onOpen() {
  SpreadsheetApp.getUi().createMenu('Pipeline')
    .addItem('Load raw sheets', 'runLoad')
    .addItem('Rebuild marts only', 'rebuildMarts')
    .addToUi();
}

/* ------------------------------------------------------------------ main */
function runLoad() {
  const started = new Date();
  const ss = SpreadsheetApp.getActive();
  const cfg = readConfig_(ss);
  const aliases = readAliases_(ss);
  const loadId = 'L' + Utilities.formatDate(started, cfg.TIMEZONE, 'yyyyMMdd-HHmmss');
  const warnings = [];

  // 1) policy sales first, so payments can be linked to them
  const salesRaw = readTable_(sheet_(ss, SHEETS.rawSales));
  const newSales = [];
  salesRaw.rows.forEach(r => {
    const ts = parseDmy_(r['Sale Date']);
    if (!ts) return;
    newSales.push([r['Sale ID'], ts, dateOnly_(ts), cleanInsurer_(r['Partner'], aliases) || '', String(r['Agent Name']).trim(),
      String(r['Policy No']).trim(), r['Policy Type'], toNumber_(r['Premium (USD)']), loadId]);
  });
  replaceDays_(ss, SHEETS.fctSales, FCT_SALES_HEADERS, newSales, 3);
  const allSales = readTable_(sheet_(ss, SHEETS.fctSales)).rows;
  const saleByPolicy = {};
  allSales.forEach(s => { saleByPolicy[String(s.policy_no)] = s; });

  // 2) payments
  const raw = readTable_(sheet_(ss, SHEETS.rawPay));
  const seen = {};
  const out = [], dq = [];
  let dupes = 0, bad = 0, flagged = 0, totalUsd = 0, dateConverted = 0;
  raw.rows.forEach(r => {
    const key = String(r['Reference']).trim();
    if (!key) { bad++; return; }
    if (seen[key]) { dupes++; return; }                      // terminal re-sync sent the row twice
    seen[key] = true;
    if (r['Txn Date'] instanceof Date) dateConverted++;
    const ts = parseDmy_(r['Txn Date']);
    if (!ts) { bad++; return; }
    const txnDate = dateOnly_(ts);
    const lbp = toNumber_(r['Amount (LBP)']);
    const usd = Math.round(lbp / cfg.LBP_PER_USD * 100) / 100;
    const insurerRaw = String(r['Insurer'] || '').trim();
    const insurer = cleanInsurer_(insurerRaw, aliases);
    const policyNo = String(r['Policy No'] || '').trim();
    const inception = parseDmy_(r['Inception Date']);
    const expiry = parseDmy_(r['Expiry Date']);
    const term = inception && expiry ? daysBetween_(inception, expiry) : '';

    const flags = [];
    if (!insurerRaw) flags.push('insurer_missing');
    else if (!insurer) flags.push('insurer_unknown');
    if (PLACEHOLDER_POLICY.indexOf(policyNo.toUpperCase()) >= 0 || policyNo.length < 4) flags.push('placeholder_policy');
    if (!inception || !expiry) flags.push('policy_details_missing');
    else if (term < cfg.MIN_TERM_DAYS || term > cfg.MAX_TERM_DAYS) flags.push('unusual_policy_term');

    let timing = 'Unknown';
    if (inception) {
      const d = daysBetween_(inception, txnDate);
      timing = d === 0 ? 'Same day' : (d > 0 ? 'Before payment' : 'After payment');
    }
    const sale = saleByPolicy[policyNo];
    const boughtHere = !!sale;
    const sameDay = boughtHere && sameDate_(sale.sale_date, txnDate);

    if (flags.length) {
      flagged++;
      dq.push([loadId, key, txnDate, r['Agent Name'], flags.join('|'), policyNo, insurerRaw,
        String(r['Inception Date'] || ''), String(r['Expiry Date'] || '')]);
    }
    totalUsd += usd;
    out.push([key, ts, txnDate, WEEKDAYS_[txnDate.getDay()], ts.getHours(), r['Agent Code'], String(r['Agent Name']).trim(),
      r['Agent Category'], lbp, usd, feeBand_(usd), insurer || 'Unknown', policyNo, inception || '', expiry || '', term,
      timing, boughtHere, sameDay, flags.join('|'), flags.length ? 'review' : 'ok', loadId]);
  });
  if (dateConverted) warnings.push(dateConverted + ' dates were already converted by Sheets - check import settings');

  const daysReplaced = replaceDays_(ss, SHEETS.fctPay, FCT_PAY_HEADERS, out, 3);
  replaceDays_(ss, SHEETS.dq, DQ_HEADERS, dq, 3, out.map(r => r[2]));   // DQ_LOG mirrors the days just loaded
  rebuildMarts();

  const dates = out.map(r => r[2].getTime());
  appendRows_(ss, SHEETS.log, LOG_HEADERS, [[loadId, started, Session.getActiveUser().getEmail() || 'unknown',
    SCRIPT_VERSION, raw.rows.length, dupes, bad, out.length, flagged, newSales.length, daysReplaced,
    dates.length ? new Date(Math.min.apply(null, dates)) : '', dates.length ? new Date(Math.max.apply(null, dates)) : '',
    Math.round(totalUsd * 100) / 100, warnings.join('; '), (new Date() - started) / 1000]]);
  return { loadId, raw: raw.rows.length, dupes, bad, loaded: out.length, flagged, sales: newSales.length, daysReplaced };
}

/* ------------------------------------------------------------------ marts */
function rebuildMarts() {
  const ss = SpreadsheetApp.getActive();
  const pays = readTable_(sheet_(ss, SHEETS.fctPay)).rows;
  const sales = readTable_(sheet_(ss, SHEETS.fctSales)).rows;
  const networkOfAgent = {};
  pays.forEach(p => { networkOfAgent[p.agent_name] = p.agent_network; });

  // MART_DAILY: date x network x insurer
  const m = {};
  const k = (d, n, i) => [isoDate_(d), n, i].join('§');
  pays.forEach(p => {
    const key = k(p.txn_date, p.agent_network, p.insurer);
    const a = m[key] || (m[key] = { d: p.txn_date, n: p.agent_network, i: p.insurer, pay: 0, usd: 0, fl: 0, sd: 0, ps: 0, prem: 0 });
    a.pay++; a.usd += Number(p.amount_usd); a.fl += p.dq_status === 'review' ? 1 : 0; a.sd += isTrue_(p.bought_here_same_day) ? 1 : 0;
  });
  sales.forEach(s => {
    const net = networkOfAgent[s.agent_name] || 'Unknown';
    const key = k(s.sale_date, net, s.insurer);
    const a = m[key] || (m[key] = { d: s.sale_date, n: net, i: s.insurer, pay: 0, usd: 0, fl: 0, sd: 0, ps: 0, prem: 0 });
    a.ps++; a.prem += Number(s.premium_usd);
  });
  const mart = Object.keys(m).sort().map(key => {
    const a = m[key];
    return [a.d, WEEKDAYS_[new Date(a.d).getDay()], a.n, a.i, a.pay, round2_(a.usd), a.fl, a.sd, a.ps, round2_(a.prem)];
  });
  writeTable_(ss, SHEETS.mart, MART_HEADERS, mart);

  // DIM_AGENT: one row per agent, with last-30-day rank and tier
  const maxDate = pays.reduce((mx, p) => Math.max(mx, new Date(p.txn_date).getTime()), 0);
  const cutoff = maxDate - 29 * 86400000;
  const ag = {};
  pays.forEach(p => {
    const t = new Date(p.txn_date).getTime();
    const a = ag[p.agent_code] || (ag[p.agent_code] = { code: p.agent_code, name: p.agent_name, net: p.agent_network,
      first: t, last: t, days: {}, pay: 0, usd: 0, pay30: 0, usd30: 0, sd: 0 });
    a.first = Math.min(a.first, t); a.last = Math.max(a.last, t); a.days[t] = 1;
    a.pay++; a.usd += Number(p.amount_usd); a.sd += isTrue_(p.bought_here_same_day) ? 1 : 0;
    if (t >= cutoff) { a.pay30++; a.usd30 += Number(p.amount_usd); }
  });
  const list = Object.keys(ag).map(c => ag[c]).sort((x, y) => y.usd30 - x.usd30);
  const dim = list.map((a, i) => {
    const since = Math.round((maxDate - a.last) / 86400000);
    const rank = a.usd30 > 0 ? i + 1 : '';
    const tier = !rank ? 'Inactive (30d)' : rank <= 50 ? 'Top 50' : rank <= 200 ? 'Top 51-200' : 'Long tail';
    return [a.code, a.name, a.net, new Date(a.first), new Date(a.last), since, since <= 7 ? 'Active' : since <= 30 ? 'Slowing' : 'Dormant',
      Object.keys(a.days).length, a.pay, round2_(a.usd), a.pay30, round2_(a.usd30), rank, tier, round2_(a.sd / a.pay)];
  });
  writeTable_(ss, SHEETS.dimAgent, DIM_AGENT_HEADERS, dim);
}

/* ------------------------------------------------------------------ helpers */
const WEEKDAYS_ = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

function sheet_(ss, name) { return ss.getSheetByName(name) || ss.insertSheet(name); }

function readConfig_(ss) {
  const cfg = { LBP_PER_USD: 89500, MIN_TERM_DAYS: 330, MAX_TERM_DAYS: 400, TIMEZONE: 'Asia/Beirut' };
  const sh = ss.getSheetByName(SHEETS.config);
  if (sh && sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, 2).getValues().forEach(([k, v]) => { if (k) cfg[k] = isNaN(v) || v === '' ? v : Number(v); });
  }
  return cfg;
}

function readAliases_(ss) {
  const map = {};
  const sh = ss.getSheetByName(SHEETS.aliases);
  if (sh && sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, 2).getValues().forEach(([alias, clean]) => {
      if (alias) map[normalize_(alias)] = clean;
    });
  }
  return map;
}

function normalize_(s) { return String(s).toLowerCase().replace(/[^a-z0-9]/g, ''); }

function cleanInsurer_(raw, aliases) {
  if (!raw) return '';
  return aliases[normalize_(raw)] || '';
}

/** "31/07/2026 14:05" or "31/07/2026" -> Date. Also accepts a Date already converted by Sheets. */
function parseDmy_(v) {
  if (v instanceof Date) return v;
  const s = String(v || '').trim();
  const m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?$/);
  if (!m) return null;
  const d = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]), Number(m[4] || 0), Number(m[5] || 0));
  return d.getDate() === Number(m[1]) ? d : null;            // rejects 31/02 etc.
}

function toNumber_(v) { return typeof v === 'number' ? v : Number(String(v).replace(/[^0-9.\-]/g, '')) || 0; }
function dateOnly_(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
function daysBetween_(a, b) { return Math.round((dateOnly_(b) - dateOnly_(a)) / 86400000); }
function sameDate_(a, b) { return isoDate_(a) === isoDate_(b); }
function isoDate_(d) { d = new Date(d); return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
function round2_(x) { return Math.round(x * 100) / 100; }
function isTrue_(v) { return v === true || String(v).toUpperCase() === 'TRUE'; }
function feeBand_(usd) { return usd <= 25 ? 'A) $25' : usd <= 35 ? 'B) $35' : usd <= 45 ? 'C) $45' : 'D) $60+'; }

/** Reads a sheet with a header row into {headers, rows:[{header: value}]} */
function readTable_(sh) {
  const lastRow = sh.getLastRow(), lastCol = sh.getLastColumn();
  if (lastRow < 1 || lastCol < 1) return { headers: [], rows: [] };
  const values = sh.getRange(1, 1, lastRow, lastCol).getValues();
  const headers = values[0].map(h => String(h).trim());
  const rows = values.slice(1).filter(r => r.some(c => c !== '' && c !== null)).map(r => {
    const o = {}; headers.forEach((h, i) => { o[h] = r[i]; }); return o;
  });
  return { headers, rows };
}

function writeTable_(ss, name, headers, rows) {
  const sh = sheet_(ss, name);
  sh.clearContents();
  sh.getRange(1, 1, 1, headers.length).setValues([headers]);
  if (rows.length) sh.getRange(2, 1, rows.length, headers.length).setValues(rows);
  sh.setFrozenRows(1);
}

function appendRows_(ss, name, headers, rows) {
  const sh = sheet_(ss, name);
  if (sh.getLastRow() === 0) { sh.getRange(1, 1, 1, headers.length).setValues([headers]); sh.setFrozenRows(1); }
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, headers.length).setValues(rows);
}

/**
 * Idempotent load: drop existing rows whose date (column dateCol, 1-based) appears in the new batch
 * (or in alsoClearDates), then write old + new. Returns how many days were replaced.
 */
function replaceDays_(ss, name, headers, newRows, dateCol, alsoClearDates) {
  const sh = sheet_(ss, name);
  const existing = sh.getLastRow() > 1 ? sh.getRange(2, 1, sh.getLastRow() - 1, headers.length).getValues() : [];
  const batchDays = {};
  newRows.forEach(r => { batchDays[isoDate_(r[dateCol - 1])] = true; });
  (alsoClearDates || []).forEach(d => { batchDays[isoDate_(d)] = true; });
  const kept = existing.filter(r => r[0] !== '' && !batchDays[isoDate_(r[dateCol - 1])]);
  const replaced = {};
  existing.forEach(r => { if (r[0] !== '' && batchDays[isoDate_(r[dateCol - 1])]) replaced[isoDate_(r[dateCol - 1])] = true; });
  writeTable_(ss, name, headers, kept.concat(newRows));
  return Object.keys(replaced).length;
}

if (typeof module !== 'undefined') module.exports = { runLoad, rebuildMarts, parseDmy_, cleanInsurer_ };
