/**
 * Local test for apps_script/Code.gs, run with Node (no Google account needed).
 * A small in-memory mock stands in for SpreadsheetApp, so the exact same
 * script that runs in Google Sheets is exercised here.
 *
 *   node tests/run_pipeline_test.js
 *
 * It loads Jul, Aug, Sep, then re-loads Sep to prove the load is idempotent,
 * and writes every output sheet to tests/output/*.csv.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..');

// ---------- minimal CSV reader (handles quotes and commas inside quotes)
function readCsv(file) {
  const text = fs.readFileSync(file, 'utf8').replace(/\r/g, '');
  const rows = []; let row = [], cell = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') q = false; else cell += ch;
    } else if (ch === '"') q = true;
    else if (ch === ',') { row.push(cell); cell = ''; }
    else if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; }
    else cell += ch;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  return rows;
}
function toCsv(values) {
  const fmt = v => v instanceof Date ? isoTs(v) : (v === null || v === undefined ? '' : String(v));
  return values.map(r => r.map(v => { const s = fmt(v); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; }).join(',')).join('\n') + '\n';
}
function isoTs(d) {
  const p = n => String(n).padStart(2, '0');
  const date = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  return (d.getHours() || d.getMinutes()) ? `${date} ${p(d.getHours())}:${p(d.getMinutes())}` : date;
}

// ---------- SpreadsheetApp mock
class Range {
  constructor(sh, r, c, nr, nc) { Object.assign(this, { sh, r, c, nr, nc }); }
  getValues() {
    const out = [];
    for (let i = 0; i < this.nr; i++) {
      const src = this.sh.data[this.r - 1 + i] || [];
      const row = [];
      for (let j = 0; j < this.nc; j++) { const v = src[this.c - 1 + j]; row.push(v === undefined ? '' : v); }
      out.push(row);
    }
    return out;
  }
  setValues(vals) {
    if (vals.length !== this.nr || vals[0].length !== this.nc) throw new Error(`setValues size mismatch on ${this.sh.name}`);
    vals.forEach((row, i) => {
      const t = this.sh.data[this.r - 1 + i] || (this.sh.data[this.r - 1 + i] = []);
      row.forEach((v, j) => { t[this.c - 1 + j] = v; });
    });
  }
}
class Sheet {
  constructor(name, data) { this.name = name; this.data = data || []; }
  getLastRow() { return this.data.length; }
  getLastColumn() { return this.data.reduce((m, r) => Math.max(m, r.length), 0); }
  getRange(r, c, nr, nc) { return new Range(this, r, c, nr || 1, nc || 1); }
  clearContents() { this.data = []; }
  setFrozenRows() {}
}
const book = {};
const ss = {
  getSheetByName: n => book[n] || null,
  insertSheet: n => (book[n] = new Sheet(n)),
};
const sandbox = {
  SpreadsheetApp: { getActive: () => ss, getUi: () => ({}) },
  Session: { getActiveUser: () => ({ getEmail: () => 'jamil@example.com' }) },
  Utilities: { formatDate: (d) => isoTs(d).replace(/[-: ]/g, '') + String(Math.floor(Math.random() * 90 + 10)) },
  console, Date, Math, String, Number, Object, JSON,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'apps_script/Code.gs'), 'utf8'), sandbox);

// seed sheets
book.CONFIG = new Sheet('CONFIG', readCsv(path.join(ROOT, 'data/seed/CONFIG.csv')));
book.DIM_INSURER = new Sheet('DIM_INSURER', readCsv(path.join(ROOT, 'data/seed/DIM_INSURER.csv')));

function load(month) {
  book.RAW_PAYMENTS = new Sheet('RAW_PAYMENTS', readCsv(path.join(ROOT, `data/raw/payments_${month}.csv`)));
  book.RAW_POLICY_SALES = new Sheet('RAW_POLICY_SALES', readCsv(path.join(ROOT, `data/raw/policy_sales_${month}.csv`)));
  const res = vm.runInContext('runLoad()', sandbox);
  console.log(month, JSON.stringify(res), '| FCT_PAYMENTS rows:', book.FCT_PAYMENTS.getLastRow() - 1);
  return res;
}

const r1 = load('2026-07'), r2 = load('2026-08'), r3 = load('2026-09');
const before = book.FCT_PAYMENTS.getLastRow();
const r4 = load('2026-09');                                   // same month again
const after = book.FCT_PAYMENTS.getLastRow();

// ---------- assertions
const assert = (cond, msg) => { if (!cond) { console.error('FAIL:', msg); process.exit(1); } console.log('pass:', msg); };
assert(before === after, `re-loading September keeps FCT_PAYMENTS at ${after - 1} rows (no duplicates)`);
assert(r4.daysReplaced === 30, 're-load reports 30 days replaced');
assert(r1.daysReplaced === 0 && r2.daysReplaced === 0 && r3.daysReplaced === 0, 'first loads replace nothing');
assert(r1.dupes + r2.dupes + r3.dupes === 140, 'all 140 re-synced duplicate rows are skipped');
const keys = new Set(book.FCT_PAYMENTS.data.slice(1).map(r => r[0]));
assert(keys.size === book.FCT_PAYMENTS.getLastRow() - 1, 'txn_key is unique in FCT_PAYMENTS');
assert(sandbox.parseDmy_('31/02/2026') === null, 'impossible dates are rejected');
assert(sandbox.parseDmy_('01/07/2026 14:05').getMonth() === 6, 'dd/mm/yyyy is read as day-first (1 July, not 7 Jan)');
const dqBefore = r1.flagged + r2.flagged + r3.flagged;
assert(book.DQ_LOG.getLastRow() - 1 === dqBefore, `DQ_LOG holds each flagged payment once (${dqBefore}) after the re-load`);
const unknownIns = book.FCT_PAYMENTS.data.slice(1).filter(r => r[11] === 'Unknown' && !String(r[19]).includes('insurer_missing'));
assert(unknownIns.length === 0, 'every non-blank insurer spelling maps to a known insurer');

// ---------- write outputs
const outDir = path.join(__dirname, 'output');
fs.mkdirSync(outDir, { recursive: true });
['FCT_PAYMENTS', 'FCT_POLICY_SALES', 'MART_DAILY', 'DIM_AGENT', 'DQ_LOG', 'LOAD_LOG'].forEach(n => {
  fs.writeFileSync(path.join(outDir, n + '.csv'), toCsv(book[n].data));
});
console.log('outputs written to', outDir);
