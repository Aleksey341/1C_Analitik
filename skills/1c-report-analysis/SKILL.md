---
id: 1c-report-analysis
name: 1C report analysis and drilldown
description: Analyze 1C reports, report lines, totals, filters, settings, drilldowns and trace reported amounts to source records and registrars.
task_types:
  - reporting
triggers:
  - "\u043e\u0442\u043a\u0443\u0434\u0430 \u0446\u0438\u0444\u0440\u0430 \u0432 \u043e\u0442\u0447\u0435\u0442\u0435"
  - "\u043e\u0442\u043a\u0443\u0434\u0430 \u0441\u0443\u043c\u043c\u0430 \u0432 \u043e\u0442\u0447\u0451\u0442\u0435"
  - "\u043e\u0442\u043a\u0443\u0434\u0430 \u0441\u0442\u0440\u043e\u043a\u0430 \u0432 \u043e\u0442\u0447\u0451\u0442\u0435"
  - "\u0440\u0430\u0441\u0448\u0438\u0444\u0440\u043e\u0432\u043a\u0430 \u043e\u0442\u0447\u0451\u0442\u0430"
  - "\u0440\u0430\u0441\u0448\u0438\u0444\u0440\u043e\u0432\u043a\u0430 \u043e\u0442\u0447\u0435\u0442\u0430"
  - "\u043f\u043e\u0447\u0435\u043c\u0443 \u043e\u0442\u0447\u0451\u0442 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442"
  - "\u043f\u043e\u0447\u0435\u043c\u0443 \u043e\u0442\u0447\u0435\u0442 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442"
  - "\u043d\u0435 \u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f \u043e\u0442\u0447\u0451\u0442\u044b"
  - "\u043d\u0435 \u0441\u0445\u043e\u0434\u044f\u0442\u0441\u044f \u043e\u0442\u0447\u0435\u0442\u044b"
  - "\u0440\u0430\u0437\u043d\u044b\u0435 \u0446\u0438\u0444\u0440\u044b \u0432 \u043e\u0442\u0447\u0451\u0442\u0430\u0445"
  - "\u043e\u0441\u0432 \u043d\u0435 \u0441\u0445\u043e\u0434\u0438\u0442\u0441\u044f"
  - "\u0441\u0442\u0440\u043e\u043a\u0430 \u043e\u0442\u0447\u0451\u0442\u0430"
  - "\u0432\u0430\u0440\u0438\u0430\u043d\u0442 \u043e\u0442\u0447\u0451\u0442\u0430"
  - "\u043d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438 \u043e\u0442\u0447\u0451\u0442\u0430"
  - "report drilldown"
  - "report discrepancy"
---

# 1C report analysis and drilldown

Use this skill when an analyst needs to understand:

- why a report contains a number or line;
- what source records form a report total;
- why two reports differ;
- whether the difference is accounting or presentation;
- how to trace a report value to a registrar and source document;
- how filters, period, grouping and report variants affect the result.

## Core principle

A report is not the accounting fact itself.

Use:

REPORT
-> PARAMETERS
-> FILTERS
-> GROUPING
-> LINE / CELL
-> DRILLDOWN
-> SOURCE RECORD
-> REGISTRAR
-> MOVEMENTS
-> SOURCE DOCUMENT
-> ECONOMIC FACT

Do not start by correcting documents merely because a report looks wrong.

## 1. Establish exactly which report is being analyzed

Record where possible:

- configuration;
- report name;
- report variant;
- organization;
- period;
- accounting contour;
- currency;
- filters;
- grouping;
- comparison value.

Do not assume two users see the same data merely because they opened a report with the same name.

## 2. Separate report presentation from source data

A difference may come from:

- different filters;
- different grouping;
- hidden selections;
- report variant;
- period boundary;
- organization;
- account selection;
- status filter;
- currency;
- inclusion/exclusion rules;
- different source records;
- actual accounting error.

Classify the difference before diagnosing the source document.

## 3. First reproduce the number

Before explaining a figure, establish:

- exact cell/row;
- amount;
- period;
- organization;
- grouping;
- active filters.

If the figure cannot be reproduced with fixed settings, first solve reproducibility.

## 4. Drill down progressively

Prefer:

TOTAL
-> GROUP
-> SUBGROUP
-> DOCUMENT / RECORD
-> REGISTRAR
-> MOVEMENT

Do not inspect random documents before localizing the amount.

## 5. Report line versus register record

A report line may aggregate many records.

Do not assume:

ONE REPORT LINE = ONE DOCUMENT.

Establish the grain.

Examples:

- account;
- counterparty;
- contract;
- nomenclature;
- warehouse;
- cost object;
- document;
- registrar.

## 6. Two reports do not have to match automatically

Before comparing two reports establish:

- do they use the same source data?
- same accounting contour?
- same period logic?
- same grain?
- same filters?
- same currency?
- same sign convention?
- same treatment of reversals?
- same inclusion rules?

Only after comparability is proven should a numerical difference be treated as a discrepancy.

When reconciliation skill is active, use its comparability rules.

## 7. Period logic

Check:

- beginning of period;
- end of period;
- inclusive/exclusive boundaries;
- document date;
- movement period;
- reporting period;
- late posting;
- corrections posted later.

Do not infer that the report uses document date merely because the user selected a month.

## 8. Filters and hidden settings

Check both visible and saved report settings where available.

A saved variant may contain:

- organization selection;
- account selection;
- status;
- warehouse;
- department;
- counterparty;
- currency;
- additional fields;
- hierarchy;
- comparison mode.

Do not treat an unseen filter as an accounting error.

## 9. Grouping

A total can remain equal while detail changes.

A detail can look different because of:

- hierarchy;
- grouping level;
- collapsed groups;
- duplicate-looking analytics;
- different presentation fields;
- different normalization.

Always separate aggregation difference from source-record difference.

## 10. Report settings versus movement changes

Use:

REPORT BEFORE
-> SETTINGS BEFORE
-> REPORT AFTER
-> SETTINGS AFTER
-> SOURCE RECORDS BEFORE/AFTER

If only settings changed, accounting may be unchanged.

If source records changed, locate the registrar.

## 11. Source tracing

For a suspicious amount:

REPORT CELL
-> DRILLDOWN
-> SOURCE ROW
-> PERIOD
-> REGISTRAR
-> MOVEMENTS
-> DOCUMENT
-> BUSINESS FACT

If exact metadata is unknown, tell the analyst how to identify the actual source in the database.

Do not invent register names.

## 12. Accounting reports

For accounting reports distinguish:

- opening balance;
- debit turnover;
- credit turnover;
- closing balance;
- account analytics;
- subaccount analytics;
- organization;
- accounting contour.

Use the accounting identity as a control where applicable:

OPENING
+ DEBIT
- CREDIT
= CLOSING

Adapt sign conventions to the actual report.

## 13. VAT reports

For VAT-related reports separate:

- report presentation;
- VAT register/source data;
- registrar;
- source document;
- accounting entries;
- tax-period logic.

Do not conclude that VAT itself changed merely because a VAT report changed.

When accounting skill is active, keep VAT analysis independent from BU/NU.

## 14. Production and cost reports

For production/cost reports establish:

- object of cost;
- department;
- production order;
- stage;
- article/item;
- quantity;
- amount;
- WIP;
- allocation result.

Do not infer a month-closing error merely from a surprising report total.

When closing skill is active, trace the report discrepancy to the earliest wrong closing input/stage.

## 15. Historical reports

Establish whether the report uses:

- stored historical records;
- current master data attributes;
- current mapping;
- dynamically calculated analytics.

A report for an old period may change if it dynamically displays current reference data.

Do not automatically call this corruption of historical accounting.

## 16. Report discrepancy diagnosis

For every discrepancy state:

FACT
What differs.

HYPOTHESIS
Why it may differ.

CHECK
What to open.

EVIDENCE
What confirms.

EXCLUSION
What disproves.

Do not jump from "reports differ" to a root cause.

## 17. Practical investigation order

Preferred order:

1. exact report and variant;
2. identical parameters;
3. identical period;
4. identical filters;
5. identical grain;
6. reproduce the total;
7. localize first differing group;
8. drill down;
9. identify source record;
10. identify registrar;
11. inspect movements;
12. relate to economic fact.

## 18. Correction discipline

Correct the report only if the problem is report settings or report logic.

Correct source accounting only if source records are proven wrong.

Do not alter accounting data to force a report to show an expected number.

## 19. Output format

When useful:

### What the report currently proves

### What it does not prove

### Parameters to fix

### First level of drilldown

### Source tracing

### Hypotheses

### Checks

For every check:

- what to open;
- what fact to find;
- what confirms;
- what excludes.

### Root cause

Only when proven.

### Correction

### Control report

## Guardrails

- Do not equate report value with economic fact without tracing the source.
- Do not invent report source registers.
- Do not invent exact menu paths.
- Do not assume two reports are comparable.
- Do not assume a changed report means changed accounting.
- Do not inspect random documents before localizing the amount.
- Do not recommend changing source data merely to make reports equal.
- Previous AI answers are not report evidence.
