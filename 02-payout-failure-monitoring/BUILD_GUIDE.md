# Build guide: Payout Failure Monitoring (Power BI Desktop)

Time needed: about 6–8 hours. Power BI Desktop is free on Windows (Microsoft Store). Build it yourself, step by step. The checks table at the end tells you the number each card should show.

---

## Part 1: Load and clean the data (Power Query)

1. Copy the `data/` folder somewhere simple, e.g. `C:\portfolio\payouts\data\`, and unzip `payouts.csv.zip` inside it (it's zipped to stay under GitHub's upload size).
2. Power BI Desktop → **Transform data** → **New Source → Blank Query**. Rename it `FolderPath`, open **Advanced Editor**, and paste the code below. Change the path to your folder and keep the final backslash.

```m
"C:\portfolio\payouts\data\" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]
```

3. Create one Blank Query per file below. Open **Advanced Editor** in each and paste the code. Name each query exactly as shown.

**Why types are set by hand:** if Power Query auto-detects types, it turns the response code `000` into the number `0`, and the join to the taxonomy breaks. Every code column is therefore typed as text on purpose.

**`ErrorTaxonomy`**
```m
let
    Source  = Csv.Document(File.Contents(FolderPath & "error_taxonomy.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {
        {"response_code", type text}, {"normalized_message", type text}, {"failure_category", type text},
        {"owner", type text}, {"severity", type text}, {"escalate", type text}, {"retry_recommended", type text}})
in
    Typed
```

**`BankNameMapping`**
```m
let
    Source  = Csv.Document(File.Contents(FolderPath & "bank_name_mapping.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {{"bank_name_raw", type text}, {"bank_id", type text}})
in
    Typed
```

**`FxRates`**
```m
let
    Source  = Csv.Document(File.Contents(FolderPath & "fx_rates.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed   = Table.TransformColumnTypes(Headers, {{"month", type text}, {"currency", type text}, {"usd_per_unit", type number}}, "en-US")
in
    Typed
```

**`DimBank`** and **`DimCountry`** use the same pattern. Load `banks.csv` and `countries.csv`, and type every column as text.

**`FactPayouts`** is the main table. Every step has a name you can explain in an interview.
```m
let
    Source            = Csv.Document(File.Contents(FolderPath & "payouts.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers           = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed             = Table.TransformColumnTypes(Headers, {
                            {"partner_txn_id", type text}, {"received_time", type datetime}, {"last_update_time", type datetime},
                            {"status", type text}, {"payout_type", type text}, {"source_country", type text},
                            {"destination_country", type text}, {"destination_currency", type text},
                            {"destination_amount", type number}, {"bank_name_raw", type text}, {"response_code", type text},
                            {"response_message", type text}, {"sender_id", type text}, {"receiver_id", type text},
                            {"retry_of", type text}}, "en-US"),
    RemovedDuplicates = Table.Distinct(Typed),                                   // partner re-sent 85 rows
    UpperStatus       = Table.TransformColumns(RemovedDuplicates, {{"status", Text.Upper, type text}}),
    BlankRetryToNull  = Table.ReplaceValue(UpperStatus, "", null, Replacer.ReplaceValue, {"retry_of"}),
    MergedBank        = Table.NestedJoin(BlankRetryToNull, {"bank_name_raw"}, BankNameMapping, {"bank_name_raw"}, "Map", JoinKind.LeftOuter),
    ExpandedBank      = Table.ExpandTableColumn(MergedBank, "Map", {"bank_id"}),
    AddedMonth        = Table.AddColumn(ExpandedBank, "month", each Date.ToText(DateTime.Date([received_time]), "yyyy-MM"), type text),
    MergedFx          = Table.NestedJoin(AddedMonth, {"month", "destination_currency"}, FxRates, {"month", "currency"}, "Fx", JoinKind.LeftOuter),
    ExpandedFx        = Table.ExpandTableColumn(MergedFx, "Fx", {"usd_per_unit"}),
    AddedUsd          = Table.AddColumn(ExpandedFx, "usd_amount", each Number.Round([destination_amount] * [usd_per_unit], 2), type number),
    AddedDate         = Table.AddColumn(AddedUsd, "date", each DateTime.Date([received_time]), type date),
    AddedHour         = Table.AddColumn(AddedDate, "hour", each Time.Hour([received_time]), Int64.Type),
    AddedExecution    = Table.AddColumn(AddedHour, "execution_s", each Duration.TotalSeconds([last_update_time] - [received_time]), type number),
    AddedIsRetry      = Table.AddColumn(AddedExecution, "is_retry", each [retry_of] <> null, type logical),
    // which error did the ORIGINAL attempt get? (needed to judge if the retry made sense)
    Originals         = Table.SelectColumns(AddedIsRetry, {"partner_txn_id", "response_code"}),
    MergedOriginal    = Table.NestedJoin(AddedIsRetry, {"retry_of"}, Originals, {"partner_txn_id"}, "Orig", JoinKind.LeftOuter),
    ExpandedOriginal  = Table.ExpandTableColumn(MergedOriginal, "Orig", {"response_code"}, {"original_code"}),
    MergedOrigTax     = Table.NestedJoin(ExpandedOriginal, {"original_code"}, ErrorTaxonomy, {"response_code"}, "OrigTax", JoinKind.LeftOuter),
    ExpandedOrigTax   = Table.ExpandTableColumn(MergedOrigTax, "OrigTax", {"retry_recommended"}, {"original_retry_recommended"}),
    // did the money arrive in the end? (first try OK, or a later retry OK)
    OkRetries         = Table.SelectRows(ExpandedOrigTax, each [is_retry] and [status] = "SUCCESS"),
    OkRetryIds        = Table.Distinct(Table.SelectColumns(OkRetries, {"retry_of"})),
    MergedOk          = Table.NestedJoin(ExpandedOrigTax, {"partner_txn_id"}, OkRetryIds, {"retry_of"}, "Ok", JoinKind.LeftOuter),
    AddedFinalSuccess = Table.AddColumn(MergedOk, "final_success",
                            each if [is_retry] then null else ([status] = "SUCCESS" or not Table.IsEmpty([Ok])), type logical),
    Cleaned           = Table.RemoveColumns(AddedFinalSuccess, {"Ok", "month", "usd_per_unit", "bank_name_raw", "response_message", "source_country"})
in
    Cleaned
```

4. Right-click `BankNameMapping`, `FxRates` and `FolderPath` and untick **Enable load**. They're helpers and don't need to appear in the model. Click **Close & Apply**.

## Part 2: Model

1. **Date table:** Modeling → **New table**:
```dax
DimDate =
ADDCOLUMNS (
    CALENDAR ( DATE ( 2026, 4, 1 ), DATE ( 2026, 9, 30 ) ),
    "Month", FORMAT ( [Date], "mmm yyyy" ),
    "Month Start", DATE ( YEAR ( [Date] ), MONTH ( [Date] ), 1 ),
    "Day of Month", DAY ( [Date] ),
    "Weekday", FORMAT ( [Date], "ddd" ),
    "Weekday Number", WEEKDAY ( [Date], 2 )
)
```
   Then **Mark as date table** (column `Date`). Sort `Month` by `Month Start`, and `Weekday` by `Weekday Number`.
2. **Relationships** (Model view, all many-to-one, single direction):
   - `FactPayouts[date]` → `DimDate[Date]`
   - `FactPayouts[bank_id]` → `DimBank[bank_id]`
   - `FactPayouts[destination_country]` → `DimCountry[country_code]`
   - `FactPayouts[response_code]` → `ErrorTaxonomy[response_code]`. Rename `ErrorTaxonomy` to `DimErrorCode`.
3. Hide the key columns on the fact table, so report users only see the dimension versions.

## Part 3: Measures

Create an empty table called `_Measures`: Enter data → one blank column → load. Put every measure in it.

```dax
Attempts = COUNTROWS ( FactPayouts )
Successful = CALCULATE ( [Attempts], FactPayouts[status] = "SUCCESS" )
Failed = CALCULATE ( [Attempts], FactPayouts[status] = "FAILED" )
Success Rate % = DIVIDE ( [Successful], [Attempts] )

Requests = CALCULATE ( [Attempts], FactPayouts[is_retry] = FALSE () )
First-try Success % = DIVIDE ( CALCULATE ( [Successful], FactPayouts[is_retry] = FALSE () ), [Requests] )
Final Success % = DIVIDE ( CALCULATE ( [Attempts], FactPayouts[final_success] = TRUE () ), [Requests] )

USD Paid Out = CALCULATE ( SUM ( FactPayouts[usd_amount] ), FactPayouts[status] = "SUCCESS" )
USD Failed = CALCULATE ( SUM ( FactPayouts[usd_amount] ), FactPayouts[status] = "FAILED" )
Median Payout Time (s) = CALCULATE ( MEDIAN ( FactPayouts[execution_s] ), FactPayouts[status] = "SUCCESS" )

Failure Share % = DIVIDE ( [Failed], CALCULATE ( [Failed], ALL ( DimErrorCode ) ) )
Bank Failure Rank = RANKX ( ALL ( DimBank[bank_name] ), [Failed] )

Retries = CALCULATE ( [Attempts], FactPayouts[is_retry] = TRUE () )
Retry Success % = DIVIDE ( CALCULATE ( [Successful], FactPayouts[is_retry] = TRUE () ), [Retries] )
Wasted Retries = CALCULATE ( [Retries], FactPayouts[original_retry_recommended] = "No" )
Wasted Retry Share % = DIVIDE ( [Wasted Retries], [Retries] )

Outage Failures = CALCULATE ( [Failed], DimErrorCode[failure_category] = "Bank / partner outage" )
Outage Rate % = DIVIDE ( [Outage Failures], [Attempts] )
Is Incident = IF ( [Outage Failures] >= 4 && [Outage Rate %] >= 0.2, 1, 0 )
Incident Days =
SUMX ( SUMMARIZE ( FactPayouts, FactPayouts[bank_id], FactPayouts[date] ), [Is Incident] )

Success Rate % PM = CALCULATE ( [Success Rate %], DATEADD ( DimDate[Date], -1, MONTH ) )
Success Rate Change vs PM = [Success Rate %] - [Success Rate % PM]
```

Format the `%` measures as Percentage with 1 decimal, and the USD measures as Currency with 0 decimals.

## Part 4: Report pages

Use one consistent layout on every page: a title bar at the top, slicers on the left (Month, Country, Payout type), and visuals on the right.

**1. Executive Overview**
- Cards: Requests, Final Success %, First-try Success %, USD Paid Out, USD Failed, Median Payout Time (s).
- Line chart: Success Rate % by `DimDate[Date]`.
- Map: `DimCountry[country_name]` with bubble size = Attempts. Tooltip: Success Rate %.
- Table by country: Attempts, Success Rate %, USD Failed.

**2. Why Payouts Fail**
- Bar chart: Failed by `DimErrorCode[failure_category]`. Legend: `owner`.
- Donut: Failed by `owner`.
- Matrix: rows `failure_category` → `normalized_message`. Values: Failed, Failure Share %.
- **Decomposition tree:** analyse Failed, explain by category → country → bank. In an interview, click through it live: Receiver details → Ethiopia → ET Bank 01.

**3. Banks & Corridors**
- Matrix by `DimBank[bank_name]`: Attempts, Success Rate %, Median Payout Time (s), Failed, Bank Failure Rank. Add conditional formatting (background colour) on Success Rate % and Median Payout Time (s). BD Bank 03 should stand out as slow (about 450 s against about 150 s).
- Scatter: x = Attempts, y = Success Rate %, details = bank.

**4. Incident Monitor**
- Matrix: rows `bank_name`, columns `DimDate[Date]`, values Outage Failures. Turn on background colour. Filter it with a relative date slicer, or a Month slicer, so it isn't too wide.
- Table: bank_name, Date, Attempts, Outage Failures, Outage Rate %. Add a **visual-level filter** of Is Incident = 1. This is the daily incident list, and it should show 6 rows.
- Card: Incident Days.

**5. Retries & Treasury**
- Clustered bar: Retries and Retry Success % by `original_retry_recommended`.
- Card: Wasted Retry Share %.
- Column chart: Failed by `DimDate[Day of Month]`, filtered to `response_code = "F01"`. This is the month-end chart.

## Part 5: Publish

- Power BI's "Publish to web" needs a work account. For a personal portfolio, do all three of these:
  1. Export each page as an image (File → Export → PDF, then take screenshots) into `images/`.
  2. Upload the `.pbix` to the GitHub repo.
  3. Optionally post it on **NovyPro** or the **Maven Analytics** portfolio page, which host Power BI reports for free.
- Record a 2-minute screen video clicking through the decomposition tree and the incident page. Recruiters watch these.

## Checks: your numbers should match

| Measure (no filters) | Expected |
|---|---|
| Attempts | 82,422 |
| Requests | 80,349 |
| Retries | 2,073 |
| Failed | 6,725 |
| Success Rate % | 91.8% |
| First-try Success % | 93.5% |
| Final Success % | 94.2% |
| USD Paid Out | $18,427,426 (±$5 from rounding) |
| USD Failed | $1,609,977 |
| Retry Success % | 26.2% |
| Wasted Retries / share | 1,581 / 76.3% |
| Outage Failures | 605 |
| Incident Days | 6 |
| Median Payout Time (s), all successful | 87 |

If **Attempts** shows 82,507, the duplicate-removal step is missing. If **Failed by category** has a blank row, `response_code` was typed as a number somewhere.
