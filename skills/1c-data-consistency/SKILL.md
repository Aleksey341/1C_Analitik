---
id: 1c-data-consistency
name: 1C data consistency and reconciliation
description: Reconcile 1C, SAP, Excel and accounting datasets and localize discrepancies.
task_types:
  - reconciliation
triggers:
  - "\u0441\u0432\u0435\u0440\u043a\u0430 1\u0441"
  - "\u0441\u0432\u0435\u0440\u043a\u0430 sap"
  - "\u0441\u0432\u0435\u0440\u043a\u0430 excel"
  - "\u0441\u0432\u0435\u0440\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445"
  - "\u0441\u0432\u0435\u0440\u0438\u0442\u044c 1\u0441"
  - "\u0441\u0432\u0435\u0440\u0438\u0442\u044c \u0441 sap"
  - "\u0441\u0432\u0435\u0440\u0438\u0442\u044c \u0441 excel"
  - "\u0440\u0430\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435 1\u0441"
  - "\u0440\u0430\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435 sap"
  - "\u0440\u0430\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435 \u043e\u0441\u0442\u0430\u0442\u043a\u043e\u0432"
  - "\u0440\u0430\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435 \u043e\u0431\u043e\u0440\u043e\u0442\u043e\u0432"
  - "\u043d\u0435 \u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f \u043e\u0441\u0442\u0430\u0442\u043a\u0438"
  - "\u043d\u0435 \u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f \u043e\u0431\u043e\u0440\u043e\u0442\u044b"
  - "\u0441\u043e\u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0435 \u0434\u0430\u043d\u043d\u044b\u0445"
  - "\u043a\u043e\u043d\u0441\u0438\u0441\u0442\u0435\u043d\u0442\u043d\u043e\u0441\u0442\u044c"
  - "\u043c\u044d\u043f\u043f\u0438\u043d\u0433"
  - "reconciliation"
  - "reconcile"
  - "data consistency"
---

# 1C data consistency and reconciliation

Use this skill when an analyst compares data between:

- 1C and SAP;
- 1C and Excel;
- ERP and accounting systems;
- two 1C reports;
- source system and target system;
- accounting and operational contours.

## Objective

Do not begin by explaining the difference.

First prove that both datasets are comparable.

Use this chain:

COMPARISON PURPOSE
-> DATASET A
-> DATASET B
-> COMMON GRAIN
-> FILTERS
-> PERIOD / CUT-OFF
-> MAPPING
-> NORMALIZATION
-> CONTROL TOTALS
-> RECORD-LEVEL DIFFERENCES
-> ROOT-CAUSE BUCKET
-> SOURCE DOCUMENT / MOVEMENT
-> CORRECTION
-> RECONCILIATION CONTROL

## 1. Establish the reconciliation question

State precisely what is being compared:

- opening balance;
- debit/credit turnover;
- closing balance;
- quantity;
- amount;
- tax amount;
- document population;
- object population;
- analytics;
- status;
- master data.

Do not compare an ending balance in one system with period turnover in another.

## 2. Define the grain

For both datasets establish the lowest meaningful comparison level.

Examples:

- organization + account;
- organization + account + counterparty;
- material + warehouse;
- fixed asset + inventory number;
- document + line;
- employee + accrual type;
- cost object + period.

Both sides must be aggregated to a compatible grain before differences
are interpreted.

A total may reconcile while detailed analytics do not.

Detailed analytics may reconcile while totals differ because of omitted rows.

## 3. Period and cut-off

Check separately:

- start date;
- end date;
- time boundary;
- posting period;
- document date;
- accounting period;
- extraction timestamp;
- whether late postings are included;
- whether closed-period corrections were loaded.

Do not assume equal labels such as "August" imply equal cut-off logic.

## 4. Scope and filters

For both datasets record:

- organization / company code;
- business unit;
- account / account range;
- warehouse;
- currency;
- ledger / accounting contour;
- document statuses;
- posted/unposted condition;
- deleted/reversed records;
- active filters;
- report variant;
- exclusions.

A filter mismatch is a reconciliation cause, not an accounting error.

## 5. Mapping

Make mapping explicit.

Typical mapping areas:

- chart of accounts;
- organizations / company codes;
- counterparties;
- contracts;
- materials / nomenclature;
- warehouses;
- cost centers;
- projects;
- fixed assets;
- employees;
- currencies;
- tax codes;
- document types.

Classify mappings:

- one-to-one;
- many-to-one;
- one-to-many;
- missing;
- ambiguous.

Never silently force an ambiguous mapping.

## 6. Normalize before comparison

Normalize where relevant:

- sign convention;
- debit / credit representation;
- currency;
- exchange-rate basis;
- decimal precision;
- units of measure;
- rounding;
- date format;
- document number format;
- leading zeros;
- text case / spaces;
- empty versus zero;
- reversal representation.

Do not explain a difference before normalization is complete.

## 7. Control totals first

Use progressive reconciliation.

Level 1:
grand total.

Level 2:
organization / account.

Level 3:
major analytic.

Level 4:
document or record.

Find the first level where the difference appears.

This reduces the search space and prevents random document inspection.

## 8. Use a reconciliation equation

For balance reconciliation verify:

OPENING
+ DEBIT / INCREASE
- CREDIT / DECREASE
= CLOSING

Adapt sign semantics to the specific accounting object.

For movement reconciliation verify separately:

- population count;
- amount;
- quantity;
- unique keys.

A matching total does not prove matching populations.

## 9. Record-level comparison

After totals are localized, classify records into:

A_ONLY
exists only in source A.

B_ONLY
exists only in source B.

MATCHED_SAME
key exists on both sides and values match.

MATCHED_DIFFERENT
key exists on both sides but amount/analytics/status differ.

DUPLICATE
one key maps to multiple rows unexpectedly.

UNMAPPED
no reliable cross-system mapping exists.

This classification is preferable to a single column "difference".

## 10. Difference buckets

Classify each difference into a root-cause bucket:

- scope/filter mismatch;
- period/cut-off mismatch;
- mapping mismatch;
- missing source document;
- missing target record;
- duplicate;
- reversal/storno interpretation;
- sign convention;
- currency/rate;
- rounding;
- unit conversion;
- different accounting rule;
- posting/status difference;
- late posting;
- integration timing;
- transformation logic;
- incorrect 1C movement;
- incorrect external-system record;
- not yet determined.

Do not put unexplained amounts into "other" without preserving traceability.

## 11. Trace discrepancy to source

For an individual 1C discrepancy use, where applicable:

reconciliation row
-> report/detail
-> source record
-> registrar
-> movements
-> source document
-> economic fact

For SAP or another source system, identify an equivalent trace key:

- document number;
- company code;
- fiscal year;
- posting key;
- material document;
- external identifier;
- integration message id.

Do not invent fields that have not been established.

## 12. Opening balance logic

When opening balances differ, do not immediately investigate current-period documents.

First establish:

- whether opening was migrated;
- previous closing balance;
- carry-forward logic;
- manual opening entries;
- historical corrections;
- account mapping changes.

If opening differs, current closing may differ even when current movements reconcile perfectly.

## 13. Turnover logic

When opening balances match but closing balances differ:

focus first on current-period movements.

When openings differ but turnovers match:

the problem is likely before the current period.

When both opening and turnover differ:

separate the two problems; do not net them.

## 14. Reversals and storno

Check whether systems represent corrections differently:

- negative posting;
- reversal document;
- separate correcting entry;
- original plus cancellation;
- net presentation.

Two systems may be economically equivalent while record populations differ.

## 15. Currency

For currency differences establish separately:

- transaction currency;
- functional/accounting currency;
- exchange-rate date;
- rate type;
- historical versus current rate;
- rounding;
- revaluation entries.

Do not compare foreign-currency amount on one side with local-currency amount
on the other without normalization.

## 16. Data extraction reproducibility

A reconciliation must be reproducible.

Record:

- extraction date/time;
- source report/query;
- parameters;
- filters;
- file version;
- data refresh timestamp.

If extracts were produced at different times, identify whether source data
changed between extracts.

## 17. Reconciliation table

For substantial reconciliation prefer a table with columns such as:

- comparison key;
- source A value;
- source B value;
- difference;
- mapping status;
- difference bucket;
- source A reference;
- source B reference;
- explanation status;
- owner, only if explicitly assigned;
- comment.

Do not mix an unexplained difference with an accepted justified difference.

## 18. Statuses

Use explicit reconciliation status:

MATCH
JUSTIFIED_DIFFERENCE
ERROR_A
ERROR_B
MAPPING_REQUIRED
TIMING_DIFFERENCE
UNDER_INVESTIGATION
BLOCKED

A difference is not automatically an error.

## 19. Evidence-driven reconciliation

For every material difference specify:

- what is known;
- what is hypothesized;
- next check;
- expected evidence;
- what would confirm;
- what would exclude.

When diagnosis skill is also active, use its evidence rules.

## 20. Correction discipline

Correct only after identifying the root cause.

Do not force systems to equal totals by:

- manual balancing entries;
- deleting unmatched rows;
- changing mapping without evidence;
- ignoring small differences;
- mass reposting.

After correction rerun the same reconciliation with identical parameters.

## Required output

When useful structure the response as:

### Reconciliation objective

### Comparability check

### Control totals

### Difference localization

### Difference buckets

### Record-level checks

### Root cause

### Correction

### Reconciliation control

### Open questions

## Guardrails

- Do not assume equal totals mean equal data.
- Do not assume unequal totals mean accounting error.
- Do not invent mappings.
- Do not invent SAP or 1C field names.
- Do not compare different periods or grains without explicitly stating it.
- Do not net opening-balance and turnover discrepancies.
- Do not treat timing difference as permanent error without evidence.
- Previous AI answers are not reconciliation evidence.
