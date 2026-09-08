---
id: 1c-closing-month
name: 1C month-end closing and cost calculation
description: Diagnose month-end closing, cost calculation, WIP, expense allocation and period-closing problems in 1C ERP and 1C Accounting.
task_types:
  - closing
triggers:
  - "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430"
  - "\u0437\u0430\u043a\u0440\u044b\u0442\u044c \u043c\u0435\u0441\u044f\u0446"
  - "\u043d\u0435 \u0437\u0430\u043a\u0440\u044b\u0432\u0430\u0435\u0442\u0441\u044f \u043c\u0435\u0441\u044f\u0446"
  - "\u043d\u0435 \u0437\u0430\u043a\u0440\u044b\u043b\u0441\u044f \u043c\u0435\u0441\u044f\u0446"
  - "\u0440\u0430\u0441\u0447\u0435\u0442 \u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438"
  - "\u0440\u0430\u0441\u0447\u0451\u0442 \u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438"
  - "\u0441\u0435\u0431\u0435\u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u043f\u043e\u0441\u043b\u0435 \u0437\u0430\u043a\u0440\u044b\u0442\u0438\u044f"
  - "\u043d\u0437\u043f"
  - "\u043d\u0435\u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043d\u043e\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0441\u0442\u0432\u043e"
  - "\u043d\u0435\u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d\u043d\u043e\u0435 \u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0441\u0442\u0432\u043e"
  - "\u0440\u0430\u0441\u043f\u0440\u0435\u0434\u0435\u043b\u0435\u043d\u0438\u0435 \u0440\u0430\u0441\u0445\u043e\u0434\u043e\u0432"
  - "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u0437\u0430\u0442\u0440\u0430\u0442"
  - "\u0440\u0435\u0433\u043b\u0430\u043c\u0435\u043d\u0442\u043d\u044b\u0435 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438"
  - "\u043f\u0435\u0440\u0435\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430"
  - "month end closing"
  - "period close"
---

# 1C month-end closing and cost calculation

Use this skill for month-end closing and period-closing problems in:

- 1C:ERP;
- 1C:Accounting;
- production accounting;
- cost calculation;
- WIP;
- expense allocation;
- regulated accounting closing.

## Objective

Do not treat "month close" as one indivisible operation.

Identify:

SYMPTOM
-> ACCOUNTING CONTOUR
-> PERIOD
-> CLOSING STAGE
-> INPUT DATA
-> DEPENDENCY
-> FAILED / CHANGED RESULT
-> SOURCE RECORD
-> REGISTRAR
-> ROOT CAUSE
-> MINIMAL CORRECTION
-> REPEAT ONLY NECESSARY STAGES
-> CONTROL RESULT

## 1. First classify the problem

Distinguish:

A. Closing does not execute.

B. Closing executes with an error.

C. Closing completes but result is economically wrong.

D. Result changes after re-closing.

E. Report differs although underlying accounting records may be correct.

F. Previous period was changed after closing.

G. Closing result differs between accounting contours.

Do not investigate all seven at once.

## 2. Establish the contour

Determine which contour is affected:

- operational accounting;
- regulated accounting;
- BU;
- NU;
- VAT;
- management accounting;
- production costing;
- inventory valuation.

A problem in one contour does not prove an error in another.

When accounting-bu-nu-vat skill is active, preserve separate BU, NU and VAT conclusions.

## 3. Establish period chronology

Record separately:

- document date;
- posting date;
- accounting period;
- closing period;
- time when the source document was changed;
- time when month closing was last executed;
- whether a previous period was reopened or corrected.

Do not infer chronology from phrases such as "yesterday" without establishing
when the closing itself was performed.

## 4. Closing is a dependency chain

Treat closing as a sequence of dependent calculations.

A later stage may be wrong because an earlier stage received wrong input.

Examples of dependency areas:

- source documents;
- inventory movements;
- production output;
- material consumption;
- WIP;
- expense recognition;
- expense allocation;
- depreciation;
- currency revaluation;
- cost calculation;
- financial result.

Do not assume the final operation is the root cause.

## 5. Diagnose from the first wrong stage

Find the earliest point where actual result diverges from expected result.

Use:

EXPECTED INPUT
-> ACTUAL INPUT
-> CALCULATION / RULE
-> ACTUAL OUTPUT
-> NEXT STAGE

If stage N already contains incorrect data, do not start debugging stage N+3.

## 6. Production and WIP

For production cases establish, where relevant:

- what was produced;
- production stage / order state;
- quantity;
- material consumption;
- release;
- WIP at beginning;
- WIP at end;
- cost items;
- department;
- cost object;
- purpose / assignment;
- allocation base;
- whether required operational documents were posted.

Do not assume all production costs must close to finished goods.

Some costs may correctly remain in WIP.

## 7. WIP diagnosis

If WIP is unexpectedly high or low, separate:

- actual unfinished production;
- incomplete document chain;
- missing material allocation;
- wrong production quantity;
- wrong cost object;
- wrong department;
- missing release;
- different recognition period;
- incorrect allocation rule.

Do not clear WIP merely because the user expects zero.

First establish the economic fact.

## 8. Cost calculation

When calculated cost is unexpected, compare:

- quantity;
- direct materials;
- direct labour if applicable;
- direct costs;
- allocated indirect costs;
- opening WIP;
- closing WIP;
- allocation bases;
- output distribution.

Use reconciliation:

AVAILABLE COST
- CLOSING WIP
= COST TO BE ALLOCATED TO OUTPUT

Adapt to the actual accounting model.

Do not claim this exact formula is the configuration algorithm unless verified.

## 9. Expense allocation

For unexplained allocation establish:

SOURCE EXPENSE
-> COST ITEM
-> ORGANIZATION
-> DEPARTMENT
-> COST OBJECT
-> ALLOCATION RULE
-> ALLOCATION BASE
-> RECIPIENTS
-> RESULT

Check whether the base is:

- absent;
- zero;
- incomplete;
- from another period;
- filtered incorrectly;
- economically inappropriate.

Do not change an allocation base merely to obtain the desired result.

## 10. Previous-period changes

If a source document from an already closed period was changed:

separate:

- what changed in the source document;
- which movements changed;
- which dependent calculations use those movements;
- which later periods depend on the changed result.

Do not automatically re-close every subsequent period.

First identify the dependency chain.

## 11. Re-closing discipline

Before re-closing ask:

- Which source data changed?
- Which closing stage depends on it?
- Which periods depend on the recalculated output?
- Can recalculation be limited to the affected chain?

Avoid mass re-posting or re-closing merely as a diagnostic experiment.

A control experiment should change one variable where possible.

## 12. Reports versus accounting records

If a report changed after closing, do not immediately conclude accounting changed.

Check:

REPORT
-> FILTERS / SETTINGS
-> DETAIL
-> SOURCE RECORD
-> REGISTRAR
-> MOVEMENTS

Separate:

- changed report presentation;
- changed register records;
- changed accounting entries;
- changed economic fact.

## 13. Accounting evidence

Use exact evidence where available:

- amount before;
- amount after;
- object;
- period;
- source document;
- registrar;
- movement;
- accounting entry;
- report drilldown.

Avoid explanations based only on the operation name "Month closing".

## 14. Error message handling

For a closing error capture:

- exact error text;
- closing stage;
- period;
- organization;
- affected object if shown;
- whether error is reproducible;
- source data referenced by the error.

Do not translate a generic technical error into an accounting conclusion without evidence.

## 15. Fixed assets and depreciation

If closing affects depreciation establish separately:

- asset;
- acceptance date;
- depreciation start;
- useful life;
- method;
- suspension where applicable;
- BU treatment;
- NU treatment;
- changes of estimates versus correction of error.

Do not force BU and NU depreciation to match merely because the difference appears during closing.

## 16. Currency revaluation

For revaluation establish:

- monetary item;
- currency;
- balance;
- rate date;
- rate used;
- accounting contour;
- prior revaluation.

Do not mix exchange differences with cost-calculation discrepancies.

## 17. Closing result changed after document modification

Use this chain:

DOCUMENT BEFORE
-> DOCUMENT AFTER
-> MOVEMENT DIFFERENCE
-> DEPENDENT CLOSING STAGE
-> RESULT BEFORE
-> RESULT AFTER

This is stronger evidence than temporal coincidence.

"Changed yesterday and result changed today" is not yet proof of causation.

## 18. Minimal correction

Correct the earliest proven wrong source.

Preferred order:

1. source master/data condition;
2. source document;
3. movement;
4. allocation setting/rule;
5. closing stage.

Do not correct downstream totals if the upstream source is wrong.

## 19. Post-correction control

After correction verify:

- source movement is correct;
- affected stage recalculates as expected;
- dependent stages are consistent;
- unaffected stages did not change unexpectedly;
- report agrees with underlying records;
- BU/NU/VAT remain independently correct where relevant.

## 20. Output structure

When useful answer as:

### Problem

### What is already known

### What is not yet proven

### Closing stage to inspect first

### Checks

For every check:

- what to open;
- what fact to find;
- what confirms the hypothesis;
- what excludes it.

### Root cause

Only when proven.

### Minimal correction

### What to recalculate

### Control after correction

## Guardrails

- Do not say "closing month is broken" without locating a stage.
- Do not recommend mass reposting as the first diagnostic step.
- Do not recommend full re-closing of all periods without dependency evidence.
- Do not invent exact 1C registers, document names or menu paths.
- Do not assume WIP must be zero.
- Do not confuse report change with accounting-record change.
- Do not infer causation from chronology alone.
- Do not fix downstream totals before checking upstream source data.
- Do not force BU, NU and VAT to agree.
- Previous AI answers are not accounting evidence.
