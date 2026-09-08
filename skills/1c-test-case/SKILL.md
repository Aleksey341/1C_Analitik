---
id: 1c-test-case
name: 1C test case design
description: Build test scenarios and acceptance checks for 1C changes, incidents and integrations.
task_types:
  - testing
triggers:
  - "\u0442\u0435\u0441\u0442-\u043a\u0435\u0439\u0441"
  - "\u0442\u0435\u0441\u0442 \u043a\u0435\u0439\u0441"
  - "\u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u0441\u0446\u0435\u043d\u0430\u0440"
  - "\u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0435 \u0441\u0446\u0435\u043d\u0430\u0440"
  - "\u0442\u0435\u0441\u0442\u043e\u0432\u044b\u0445 \u0441\u0446\u0435\u043d\u0430\u0440"
  - "\u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439 \u043f\u0440\u043e\u0432\u0435\u0440\u043a"
  - "\u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 \u0434\u043e\u0440\u0430\u0431\u043e\u0442\u043a"
  - "\u043f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0434\u043e\u0440\u0430\u0431\u043e\u0442\u043a"
  - "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0435\u043c\u043a"
  - "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0451\u043c\u043a"
  - "\u043f\u0440\u0438\u0435\u043c\u043e\u0447\u043d\u043e\u0435 \u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d"
  - "\u043f\u0440\u0438\u0451\u043c\u043e\u0447\u043d\u043e\u0435 \u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d"
  - "\u0440\u0435\u0433\u0440\u0435\u0441\u0441\u0438\u043e\u043d\u043d\u043e\u0435 \u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u043d"
  - "\u043f\u0440\u043e\u0442\u0435\u0441\u0442\u0438\u0440\u043e\u0432\u0430\u0442\u044c"
  - "uat"
  - "test case"
  - "acceptance test"
  - "regression test"
---

# 1C test case design

Use this skill when an analyst must verify a 1C change, bug fix,
integration, accounting result or business requirement.

## Objective

A test must prove a requirement or hypothesis.

Do not create a list of clicks without stating what each test proves.

For every important scenario determine:

PRECONDITIONS
-> INPUT DATA
-> ACTION
-> EXPECTED RESULT
-> ACCOUNTING / REGISTER RESULT WHEN RELEVANT
-> WHAT MUST NOT CHANGE
-> PASS / FAIL CRITERION

## 1. Link tests to requirements

Every material test should answer:

- which requirement is being tested;
- which business rule is being tested;
- which risk is being controlled;
- what observable result proves success.

Do not test functionality independently from its acceptance rule.

## 2. Minimum scenario set

When relevant include:

- positive scenario;
- negative scenario;
- boundary scenario;
- permissions scenario;
- duplicate / repeated execution scenario;
- correction / cancellation scenario;
- closed-period scenario;
- integration failure scenario;
- regression scenario.

Do not force irrelevant scenarios.

## 3. Preconditions

State clearly:

- configuration / release if known;
- organization;
- period;
- relevant settings;
- user role;
- master data;
- initial balances / documents;
- whether period is open or closed;
- external-system state for integrations.

Do not assume hidden initial data.

## 4. Test data

Use explicit values whenever supplied.

If values are not supplied, either:

- use symbolic values such as X, Y, N;
- or clearly mark sample data as test data.

Never present invented test values as facts from the case.

## 5. Steps

For each step specify:

- user or system action;
- object being acted on;
- relevant parameters;
- observable intermediate result where necessary.

Avoid excessive UI detail unless the exact interface is known.

Do not invent exact menu paths, buttons or metadata names.

## 6. Expected result

Expected result must be observable and testable.

Bad:

"Document works correctly."

Good:

"After posting, the order is created once, contains N expected rows,
and no duplicate is created on repeated import."

When accounting is involved, verify separately where relevant:

- BU;
- NU;
- VAT;
- operational registers;
- totals;
- period;
- registrar;
- analytics.

## 7. What must not change

For changes affecting existing functionality explicitly verify:

- unrelated documents;
- other organizations;
- other periods;
- unrelated analytics;
- previously correct reports;
- permissions;
- existing integrations.

A fix is not successful if it corrects one result and breaks another.

## 8. Boundary cases

Test values around meaningful boundaries:

- threshold - 1;
- threshold;
- threshold + 1;
- empty value;
- minimum / maximum allowed value;
- date at period boundary;
- first / last day;
- zero quantity / zero amount where allowed;
- duplicate key;
- one item versus many items.

Use only boundaries relevant to the rule.

## 9. Repeated execution and idempotency

For imports, exchanges and processing operations test:

- first execution;
- repeated execution with identical data;
- repeated execution with modified data;
- partially processed state;
- interrupted processing;
- retry after failure.

Determine whether repeated execution must:

- do nothing;
- update;
- create a version;
- create a new object;
- return an error.

Do not assume the behaviour.

## 10. Rights

When rights matter test at least:

- authorized user;
- unauthorized user;
- user with partial rights.

Verify both:

- interface access;
- actual data/action permission.

Opening a form does not prove permission to perform the underlying operation.

## 11. Accounting verification

When testing accounting behaviour, do not stop at the document form.

Verify:

document
-> movements
-> period
-> registrar
-> analytics
-> report result

When BU, NU and VAT are involved, test each contour independently.

## 12. Integration verification

For integrations verify:

- matching rule;
- duplicate handling;
- missing identifier;
- invalid data;
- unavailable destination;
- retry;
- partial success;
- reconciliation;
- audit trail;
- repeated message.

Do not define only the happy path.

## 13. Bug-fix testing

For an incident fix include:

A. REPRODUCTION TEST

Shows that the old behaviour can be reproduced before the fix.

B. FIX TEST

Shows that the corrected behaviour now occurs.

C. REGRESSION TEST

Shows that related previously working behaviour remains unchanged.

D. CONTROL TEST

Changes one relevant variable to verify the diagnosed cause.

Do not declare a defect fixed merely because the original example now passes.

## 14. Acceptance format

When useful use:

### TC-ID

### Requirement

### Purpose

### Preconditions

### Test data

### Steps

### Expected result

### What must not change

### Actual result

### Status

PASS / FAIL / BLOCKED

## 15. GIVEN / WHEN / THEN

For business acceptance criteria prefer:

GIVEN
the initial state.

WHEN
the action occurs.

THEN
the observable expected result.

AND
what must not change.

Example:

GIVEN
an order with external number X already exists.

WHEN
the same source file is imported again.

THEN
a second order is not created.

AND
the existing order is not modified unless an explicit update rule applies.

## Guardrails

- Do not invent exact 1C metadata names.
- Do not invent exact UI paths when configuration/release is unknown.
- Do not treat sample test data as facts.
- Do not omit expected results.
- Do not omit negative scenarios where failure is plausible.
- Do not mark a test PASS without observed evidence.
- Do not mix expected result with actual result.
- Do not assume repeated execution behaviour.
- Previous AI answers are not test evidence.
