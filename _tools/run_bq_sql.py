"""
Test harness: runs BigQuery-dialect .sql files locally.
Loads every CSV in <project>/data into a DuckDB schema named <dataset>,
transpiles each statement BigQuery -> DuckDB with sqlglot, executes it,
and prints the results. Exits non-zero on the first failure.

usage: python _tools/run_bq_sql.py <project_dir> <dataset> [--quiet] [--json out.json]
"""
import sys, json
from pathlib import Path
import duckdb, sqlglot

proj, dataset = Path(sys.argv[1]), sys.argv[2]
quiet = "--quiet" in sys.argv
out_json = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None

con = duckdb.connect()
con.execute(f"CREATE SCHEMA {dataset}")
con.execute("CREATE MACRO initcap(s) AS upper(s[1]) || lower(s[2:])")
for csv in sorted((proj / "data").glob("*.csv")):
    con.execute(f"CREATE TABLE {dataset}.{csv.stem} AS SELECT * FROM read_csv_auto('{csv}', header=true, sample_size=-1)")

results = {}
for f in sorted((proj / "sql").glob("*.sql")):
    stmts = [s for s in sqlglot.parse(f.read_text(), read="bigquery") if s is not None]
    for i, st in enumerate(stmts, 1):
        duck = st.sql(dialect="duckdb")
        key = f"{f.name}#{i}"
        try:
            rel = con.sql(duck)
        except Exception as e:
            print(f"\n!! FAILED {key}\n{duck}\n{e}")
            sys.exit(1)
        if rel is None:
            print(f"ok   {key} (DDL)")
            continue
        df = rel.df()
        results[key] = json.loads(df.to_json(orient="records", date_format="iso"))
        print(f"ok   {key}  rows={len(df)}")
        if not quiet:
            print(df.head(40).to_string(index=False))
if out_json:
    Path(out_json).write_text(json.dumps(results, indent=1, default=str))
