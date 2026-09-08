---
id: evidence-driven-diagnosis
name: Evidence-driven diagnosis
description: Diagnose accounting and 1C problems by evidence instead of guessing.
task_types:
  - diagnosis
triggers:
  - "\u043e\u0448\u0438\u0431\u043a"
  - "\u043f\u043e\u0447\u0435\u043c\u0443"
  - "\u043f\u0440\u0438\u0447\u0438\u043d"
  - "\u0434\u0438\u0430\u0433\u043d\u043e\u0441\u0442"
  - "\u0440\u0430\u0441\u0445\u043e\u0436\u0434"
  - "\u043d\u0435 \u0441\u0445\u043e\u0434"
  - "\u043d\u0435 \u0437\u0430\u043f\u043e\u043b\u043d"
  - "\u043d\u0435 \u043e\u0442\u0440\u0430\u0436"
  - "\u043d\u0435\u0432\u0435\u0440\u043d"
  - "\u0447\u0442\u043e \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c"
  - "\u043a\u0430\u043a \u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c"
  - "\u0440\u0435\u0433\u0438\u0441\u0442\u0440"
  - "\u0434\u0432\u0438\u0436\u0435\u043d"
  - "\u043f\u0440\u043e\u0432\u043e\u0434\u043a"
  - "\u0437\u0430\u043a\u0440\u044b\u0442\u0438\u0435 \u043c\u0435\u0441\u044f\u0446\u0430"
  - "diagnos"
  - "root cause"
  - "why"
  - "reconcile"
---

# Evidence-driven diagnosis

Use this skill when the user needs to understand WHY a result occurred,
where a discrepancy came from, or what should be checked before changing data.

## Objective

Move from symptom to proven cause.

Do not begin with a correction.
First establish evidence.

Use this chain whenever applicable:

SYMPTOM
-> RESULT / REPORT
-> DRILLDOWN
-> SOURCE RECORD
-> REGISTER
-> REGISTRAR
-> MOVEMENTS
-> SOURCE DOCUMENT OR OPERATION
-> ECONOMIC FACT
-> ROOT CAUSE
-> MINIMAL CORRECTION
-> CONTROL RESULT

## 1. Separate epistemic status

Clearly distinguish:

- FACT: directly supported by data, document, movement, setting or user statement.
- CONCLUSION: follows from established facts.
- HYPOTHESIS: plausible but not yet proven.

Never present a hypothesis as an established fact.

## 2. Start from the observable symptom

State precisely:

- what is wrong;
- where it is visible;
- expected result;
- actual result;
- period;
- organization / business unit / object if relevant;
- BU, NU, VAT or operational contour.

Do not diagnose from a vague phrase such as "1C calculated incorrectly".

## 3. Build a small hypothesis set

Usually create 2-4 testable hypotheses.

For every hypothesis specify:

- WHAT to check;
- WHAT FACT is being sought;
- WHAT result CONFIRMS the hypothesis;
- WHAT result EXCLUDES the hypothesis.

Avoid lists of checks that do not explain what each check proves.

## 4. 1C diagnostic direction

For report discrepancies prefer:

report result
-> report drilldown
-> source record
-> record period
-> registrar
-> registrar movements
-> source document
-> related analytics
-> economic fact

When exact metadata names are unknown, describe the type of register,
movement or analytic instead of inventing a configuration object name.

## 5. Check period separately from allocation

Always distinguish:

A. WHEN the economic fact belongs to a period.

B. WHERE the amount is allocated:
   stock,
   cost of sales,
   production,
   WIP,
   finished goods,
   expenses,
   settlements,
   tax registers.

A change in allocation does not automatically change the recognition period.

## 6. Separate accounting contours

When applicable, diagnose separately:

- BU;
- tax accounting / profit tax;
- VAT;
- operational accounting.

Do not assume that the same document date or period must apply identically
to all contours.

## 7. Do not trust document labels alone

A document name, operation type, act name or report row is not proof of
economic substance.

Check:

- contract terms;
- primary facts;
- ownership / obligation / right;
- movement period;
- registrar;
- analytics;
- subsequent dependent calculations.

## 8. Use a one-variable control experiment

When two interpretations are possible, change ONE fact only.

Specify:

- changed variable;
- facts that remain unchanged;
- expected result under interpretation A;
- expected result under interpretation B.

If the conclusion changes only when that variable changes, it is evidence
that the variable is causally important.

## 9. Correction discipline

Before changing a closed period or mass reposting documents prove:

1. the economic fact;
2. the correct accounting treatment;
3. the actual 1C movement that produced the result;
4. the local source of the error;
5. dependent calculations;
6. expected changes after correction;
7. what MUST NOT change.

Prefer the smallest correction that fixes the proven cause.

Do not recommend mass reposting, deleting movements, reopening the year,
or changing document dates merely as a diagnostic experiment in production.

## 10. Required diagnostic output

For a complex incident, structure the response as:

### Short conclusion

What is currently most likely, with confidence proportional to evidence.

### Established facts

Only facts supported by the case.

### Hypotheses

2-4 testable hypotheses if the cause is not already proven.

### Checks

For each check:

- where / what to inspect;
- fact sought;
- confirms;
- excludes.

### Root cause

Only when sufficiently proven.

### Minimal correction

The narrowest justified action.

### Control after correction

Specify concrete expected results and values/objects to compare.

## Guardrails

- Never fabricate exact 1C register, document, field or metadata names.
- Never introduce amounts, dates, percentages or document numbers absent
  from the current case unless they are explicitly calculated from supplied data.
- Previous AI answers are not evidence.
- A report presentation is not automatically the period of the underlying record.
- Date of document is not automatically date of economic fact.
- Correlation between two changes does not prove causation.
