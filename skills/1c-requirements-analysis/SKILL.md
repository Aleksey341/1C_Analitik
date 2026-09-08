---
id: 1c-requirements-analysis
name: 1C requirements analysis
description: Turn vague business requests into testable requirements for 1C/ERP.
task_types:
  - requirements
triggers:
  - "\u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d"
  - "\u0431\u0438\u0437\u043d\u0435\u0441-\u0442\u0440\u0435\u0431\u043e\u0432\u0430\u043d"
  - "\u043f\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a"
  - "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0435 \u0437\u0430\u0434\u0430\u043d\u0438\u0435"
  - "\u0442\u0437"
  - "as-is"
  - "to-be"
  - "gap"
  - "\u0434\u043e\u0440\u0430\u0431\u043e\u0442\u043a"
  - "\u0430\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0437"
  - "\u043f\u0440\u043e\u0446\u0435\u0441\u0441"
  - "\u0431\u0438\u0437\u043d\u0435\u0441-\u043f\u0440\u043e\u0446\u0435\u0441\u0441"
  - "\u0438\u043d\u0442\u0435\u0433\u0440\u0430\u0446"
  - "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0435\u043c\u043a"
  - "\u043a\u0440\u0438\u0442\u0435\u0440\u0438\u0438 \u043f\u0440\u0438\u0451\u043c\u043a"
  - "\u0447\u0442\u043e \u0445\u043e\u0447\u0435\u0442 \u0437\u0430\u043a\u0430\u0437\u0447\u0438\u043a"
  - "\u0447\u0442\u043e \u0441\u043f\u0440\u043e\u0441\u0438\u0442\u044c \u0443 \u0437\u0430\u043a\u0430\u0437\u0447\u0438\u043a\u0430"
  - "\u043e\u0431\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d"
---

# 1C requirements analysis

Use this skill when an analyst must transform a vague request,
business problem or meeting discussion into a precise and testable
requirement for 1C:Enterprise / 1C:ERP or an integrated system.

## Objective

Do not jump from "the user wants a button/report/integration"
directly to a technical solution.

Establish:

BUSINESS GOAL
-> CURRENT PROCESS (AS-IS)
-> PROBLEM / GAP
-> TARGET PROCESS (TO-BE)
-> BUSINESS RULES
-> DATA
-> ROLES AND RIGHTS
-> INTEGRATIONS
-> EXCEPTIONS
-> NON-FUNCTIONAL CONSTRAINTS
-> ACCEPTANCE CRITERIA
-> OPEN QUESTIONS
-> IMPLEMENTATION OPTIONS

## 1. Separate problem from requested solution

A stakeholder's proposed solution is not automatically the requirement.

Example:

"Add a button that recalculates the document"

is a proposed solution.

The actual requirement may be:

"The user must be able to obtain the correct calculated amount
after changing parameter X without reopening the document."

Always identify:

- business problem;
- desired result;
- proposed implementation;
- whether the implementation is mandatory or only an idea.

## 2. Establish business goal

Determine:

- who needs the change;
- what business result is required;
- why the current process is insufficient;
- what risk, loss, manual work or delay is being eliminated;
- how success will be measured.

Do not design functionality before understanding the goal.

## 3. Describe AS-IS

Capture the current process:

- trigger / starting event;
- participants;
- source data;
- sequence of actions;
- 1C documents or functional areas involved, if known;
- external systems;
- manual operations;
- approvals;
- outputs;
- pain points;
- exceptions.

Do not invent exact metadata names if they have not been established.

## 4. Describe TO-BE

Define what must change:

- new sequence of actions;
- automation points;
- decisions;
- required data;
- responsible roles;
- expected result;
- exceptions;
- interaction with existing processes.

Do not describe TO-BE only as interface changes.

## 5. Identify the GAP

For every meaningful gap state:

AS-IS:
what happens now.

TO-BE:
what must happen.

GAP:
what capability is missing.

IMPACT:
what business consequence the gap creates.

Do not call every inconvenience a functional gap.

## 6. Business rules

Extract explicit rules such as:

- conditions;
- thresholds;
- formulas;
- dates and periods;
- statuses;
- priorities;
- approvals;
- prohibitions;
- dependencies;
- mandatory fields;
- default values.

For every rule seek:

- input;
- condition;
- result;
- exception.

Example:

IF condition
THEN result
EXCEPT when exception.

## 7. Data requirements

Determine:

- source of each material field;
- master data involved;
- owner of the data;
- required analytics;
- period / effective date;
- data quality requirements;
- whether historical values must be preserved;
- whether values are entered, calculated or received externally.

Never assume that a visible report value is stored directly.

## 8. Roles and access

Determine:

- who creates;
- who edits;
- who approves;
- who posts;
- who views;
- who may cancel or correct;
- segregation-of-duties constraints;
- organization / subdivision / warehouse / other scope restrictions.

Ability to open a document does not prove access to all underlying data.

## 9. Integrations

For each integration determine:

- source system;
- target system;
- business owner;
- data set;
- direction;
- trigger;
- frequency;
- identifier / matching rule;
- create/update/delete behaviour;
- duplicate handling;
- error handling;
- retry;
- reconciliation;
- audit trail.

Do not reduce integration requirements to "exchange data between systems".

## 10. Exceptions and negative scenarios

Ask what happens when:

- required data is absent;
- value is invalid;
- period is closed;
- source system is unavailable;
- duplicate arrives;
- user lacks rights;
- approval is rejected;
- operation is cancelled;
- document is changed after downstream processing.

A requirement without exceptions is usually incomplete.

## 11. Non-functional constraints

When relevant capture:

- performance;
- volume;
- concurrency;
- response time;
- availability;
- auditability;
- security;
- regulatory constraints;
- data retention;
- usability;
- backward compatibility.

Do not invent numerical SLA values.

## 12. Standard functionality versus development

Do not assume a customization is required.

Classify the solution as one of:

- standard 1C functionality;
- configuration / settings;
- organizational-process change;
- report / data composition adjustment;
- extension;
- integration;
- custom development;
- unknown until the specific configuration/release is inspected.

Never promise that a standard capability exists without verifying it
for the actual configuration and release.

## 13. Acceptance criteria

Every important requirement must be testable.

Prefer:

GIVEN
initial state / data.

WHEN
user or system action.

THEN
observable result.

AND
what must not change.

Include:

- positive scenario;
- boundary case;
- negative scenario;
- permissions where relevant;
- accounting consequences where relevant.

Avoid criteria such as:

"works correctly"
"convenient"
"fast"
"as expected"

unless measurable conditions are added.

## 14. Open questions

Do not hide missing information.

Group unresolved items into:

- business-rule questions;
- accounting-methodology questions;
- data questions;
- 1C configuration questions;
- integration questions;
- role/access questions;
- acceptance questions.

Ask only questions that can change the design or acceptance result.

## 15. Meeting mode

When analysing a live discussion, identify separately:

FACTS
what participants explicitly established.

DECISIONS
what they agreed to.

ASSUMPTIONS
what is being treated as true but is not yet proven.

OPEN QUESTIONS
what still requires an answer.

ACTIONS
who must do what next, if assigned.

RISKS
what may block implementation or acceptance.

Do not transform an assumption into a decision.

## 16. Required output for a substantial requirement

Use when appropriate:

### Business goal

### AS-IS

### Problem / GAP

### TO-BE

### Business rules

### Data

### Roles and rights

### Integrations

### Exceptions

### Acceptance criteria

### Open questions

### Risks

### Recommended next step

Do not force every section when it is irrelevant.

## Guardrails

- Do not invent functionality, configuration objects or metadata names.
- Do not convert stakeholder wishes into confirmed requirements without validation.
- Do not assume a proposed UI element is the real business requirement.
- Do not omit negative scenarios.
- Do not call a requirement complete without acceptance criteria.
- Do not mix fact, assumption and decision.
- Do not design development before the business goal and gap are understood.
- Previous AI answers are not evidence.
