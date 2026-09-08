---
id: accounting-bu-nu-vat
name: BU NU VAT accounting analysis
description: Separate bookkeeping, profit-tax accounting and VAT when analysing 1C accounting cases.
task_types:
  - accounting
triggers:
  - "\u0431\u0443"
  - "\u043d\u0443"
  - "\u043d\u0434\u0441"
  - "\u043d\u0430\u043b\u043e\u0433 \u043d\u0430 \u043f\u0440\u0438\u0431\u044b\u043b\u044c"
  - "\u0432\u0445\u043e\u0434\u043d\u043e\u0439 \u043d\u0434\u0441"
  - "\u0432\u044b\u0447\u0435\u0442"
  - "\u0432\u043e\u0441\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d"
  - "\u0432\u0440\u0435\u043c\u0435\u043d\u043d\u0430\u044f \u0440\u0430\u0437\u043d\u0438\u0446"
  - "\u043f\u043e\u0441\u0442\u043e\u044f\u043d\u043d\u0430\u044f \u0440\u0430\u0437\u043d\u0438\u0446"
  - "\u043f\u043d\u043e"
  - "\u043f\u043d\u0430"
  - "\u043e\u043d\u043e"
  - "\u043e\u043d\u0430"
  - "\u0430\u0432\u0430\u043d\u0441\u043e\u0432\u044b\u0439 \u043d\u0434\u0441"
  - "\u043a\u043d\u0438\u0433\u0430 \u043f\u043e\u043a\u0443\u043f\u043e\u043a"
  - "\u043a\u043d\u0438\u0433\u0430 \u043f\u0440\u043e\u0434\u0430\u0436"
  - "\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u0438\u0440\u043e\u0432\u043e\u0447\u043d\u044b\u0439 \u0441\u0447\u0435\u0442-\u0444\u0430\u043a\u0442\u0443\u0440"
  - "\u043a\u043e\u0440\u0440\u0435\u043a\u0442\u0438\u0440\u043e\u0432\u043a\u0430 \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u0438"
  - "vat"
  - "profit tax"
---

# BU / NU / VAT analysis

Use this skill when one economic event may have different recognition,
period, amount or document requirements in:

- bookkeeping / accounting (BU);
- profit-tax accounting (NU);
- VAT.

## Objective

Never collapse BU, NU and VAT into one conclusion.

For every material accounting case determine separately:

1. WHAT economic fact occurred;
2. WHEN it occurred;
3. WHAT amount belongs to the fact;
4. WHICH accounting contour is being analysed;
5. WHICH document or legal condition is required for that contour;
6. HOW 1C reflected it;
7. WHETHER differences between contours are justified.

## 1. Start from the economic fact

Before analysing postings or tax registers establish:

- what changed economically;
- which party acquired a right or obligation;
- whether ownership, price, liability, revenue, expense or tax base changed;
- whether the fact already existed at the reporting date;
- whether a later document merely confirms an earlier fact or creates a new one.

Document date is not automatically economic-fact date.

## 2. BU

For bookkeeping determine separately:

- recognition date;
- measurement / amount;
- asset, liability, income or expense affected;
- whether the information relates to conditions existing at reporting date;
- whether this is a current-period fact, confirming information,
  estimate change, or prior-period error;
- whether financial statements are already prepared or approved;
- whether the amount must be allocated among stock, COGS, production,
  WIP, finished goods or other objects.

Do not confuse recognition period with allocation of amount.

## 3. NU / profit tax

For profit-tax accounting independently determine:

- tax qualification of the operation;
- applicable recognition method;
- date of income or expense recognition;
- whether acquisition cost or previously recognized expense changes;
- effect on direct / indirect expenses where relevant;
- effect on unsold stock, WIP, finished goods and sold output;
- whether prior tax base or declaration may require correction.

Do not automatically copy the BU conclusion into NU.

A BU/NU difference is not automatically an error.

First determine whether it follows from different accounting rules.

## 4. VAT

VAT must be analysed independently.

First identify the exact VAT mechanism.

Possible mechanisms include, depending on the case:

- output VAT on sale;
- VAT on advance received;
- deduction of VAT previously calculated from advance;
- input VAT;
- input VAT deduction;
- VAT adjustment due to price/quantity change;
- correction document consequences;
- required restoration of previously deducted VAT;
- other specific statutory mechanism.

Do not call every VAT change "restoration".

Do not call every VAT difference "advance VAT".

## 5. Price changes and discounts

When price changes retrospectively determine:

- whether the contract changes the price of previously supplied goods;
- whether the payment is instead a bonus/reward not changing price;
- whether the right to discount was automatic or discretionary;
- when the condition became unconditional;
- whether a correction invoice/document is required for VAT;
- whether input VAT was previously deducted;
- what amount of VAT changes;
- which period the VAT rule assigns to the correction.

The economic period of the discount in BU/NU does not automatically
determine the VAT period.

## 6. Advances and foreign currency

For advances distinguish:

- 100% prepayment;
- partial prepayment;
- postpayment;
- monetary liability / receivable;
- non-monetary prepaid part.

Before discussing exchange differences identify exactly what monetary
asset, claim or liability is being revalued.

Do not automatically revalue an advance.

For VAT separately determine whether advance VAT arose and how it is
later offset or deducted.

## 7. Subsequent documents

When a document arrives later ask:

A. Did the underlying condition already exist at the reporting date?

B. Or did the later decision/document create a genuinely new fact?

If the later document only confirms an earlier unconditional fact,
its date does not automatically move BU/NU recognition into the later period.

VAT may still follow its own documentary rule.

## 8. 1C analysis

For each contour determine:

BU:
- postings / accounting records;
- period;
- registrar;
- analytics.

NU:
- tax accounting movements / tax attributes;
- period;
- differences with BU;
- registrar.

VAT:
- VAT registers relevant to the specific mechanism;
- registrar;
- tax period;
- source document;
- book of purchases / sales effect when applicable.

Do not invent exact register names if configuration/release is unknown.

## 9. Differences

When BU, NU and VAT differ classify the difference:

- justified by different rules;
- caused by different document requirements;
- caused by different period rules;
- caused by different source data;
- caused by incorrect 1C movements;
- not yet proven.

Never "align" contours merely because they differ.

## 10. Required output

For a complex case use:

### Economic fact

What happened economically.

### BU

- period;
- amount;
- object affected;
- evidence/checks.

### NU

- period;
- tax qualification;
- amount;
- evidence/checks.

### VAT

- exact VAT mechanism;
- document requirement;
- period;
- amount;
- evidence/checks.

### Differences

Which differences are expected and which require investigation.

### 1C verification

What movements/registrars/analytics prove the result.

### Correction

Minimum justified correction for each contour.

### Control

What should change and what should remain unchanged.

## Guardrails

- Do not merge BU, NU and VAT into one period automatically.
- Do not infer VAT treatment only from BU treatment.
- Do not invent tax consequences without establishing the economic fact.
- Do not fabricate amounts, dates, percentages or document numbers.
- Do not fabricate 1C metadata names.
- Previous AI answers are not evidence.
