---
id: meeting-analyst
name: Live meeting analyst
description: Extract facts, decisions, questions, actions and risks from a live analyst meeting.
task_types:
  - meeting
triggers:
  - "\u043d\u0430 \u0432\u0441\u0442\u0440\u0435\u0447\u0435"
  - "\u043d\u0430 \u0441\u043e\u0437\u0432\u043e\u043d\u0435"
  - "\u0432\u043e \u0432\u0440\u0435\u043c\u044f \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  - "\u0447\u0442\u043e \u0441\u043f\u0440\u043e\u0441\u0438\u0442\u044c"
  - "\u0447\u0442\u043e \u0441\u043f\u0440\u043e\u0441\u0438\u0442\u044c \u0441\u0435\u0439\u0447\u0430\u0441"
  - "\u0447\u0442\u043e \u0443\u0442\u043e\u0447\u043d\u0438\u0442\u044c"
  - "\u0447\u0442\u043e \u0440\u0435\u0448\u0438\u043b\u0438"
  - "\u043a\u0430\u043a\u0438\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u044f"
  - "\u043f\u043e\u0434\u0432\u0435\u0434\u0438 \u0438\u0442\u043e\u0433\u0438 \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  - "\u043f\u043e\u0434\u0432\u0435\u0434\u0438 \u0438\u0442\u043e\u0433\u0438 \u044d\u0442\u043e\u0439 \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  - "\u0438\u0442\u043e\u0433\u0438 \u044d\u0442\u043e\u0439 \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  - "\u0441\u0430\u043c\u043c\u0430\u0440\u0438 \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  - "\u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b \u0432\u0441\u0442\u0440\u0435\u0447\u0438"
  - "\u0441\u0442\u0435\u043d\u043e\u0433\u0440\u0430\u043c\u043c"
  - "\u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u0443\u0439 \u0440\u0435\u0448\u0435\u043d\u0438\u044f"
  - "\u0437\u0430\u0444\u0438\u043a\u0441\u0438\u0440\u0443\u0439 \u043f\u043e\u0440\u0443\u0447\u0435\u043d\u0438\u044f"
  - "meeting summary"
---

# Live meeting analyst

Use this skill when helping an analyst during or immediately after a meeting.

## Objective

Convert an imperfect live conversation into actionable analyst information.

Do not rewrite the whole transcript.

Separate:

FACTS
DECISIONS
ASSUMPTIONS
OPEN QUESTIONS
ACTIONS
RISKS

Never turn an assumption into a fact or decision.

## 1. Facts

A fact is something explicitly established in the conversation.

Preserve:

- system / configuration if stated;
- business process;
- current behaviour;
- dates;
- amounts;
- roles;
- known restrictions;
- observed error;
- confirmed requirement.

Do not fill gaps from general knowledge.

## 2. Decisions

Record a decision only when participants actually agreed.

Examples:

- agreed target behaviour;
- chosen option;
- accepted responsibility;
- agreed deadline;
- agreed business rule.

Discussion of an option is not a decision.

Words such as "maybe", "probably", "we could", "let us consider"
normally indicate an assumption or option, not a decision.

## 3. Assumptions

Explicitly mark statements being treated as true but not yet proven.

Examples:

- "probably this is caused by closing";
- "it seems standard functionality can do it";
- "most likely SAP sends this field".

Do not silently convert assumptions into facts.

## 4. Open questions

Capture questions whose answers can change:

- accounting treatment;
- requirement;
- design;
- test result;
- integration;
- period;
- responsibility;
- deadline.

Do not clutter the list with questions that have already been answered.

## 5. Actions

An action must include, when available:

- responsible person;
- action;
- object/result;
- deadline.

If responsible person or deadline was not stated, do not invent it.

Use:

OWNER ? ACTION ? DEADLINE

Unknown values should remain explicitly unknown.

## 6. Risks

Identify concrete risks supported by the conversation.

Examples:

- unclear business rule;
- no unique identifier;
- closed accounting period;
- dependency on another system;
- missing access;
- conflicting requirements;
- acceptance criterion absent.

Do not produce generic project-risk boilerplate.

## 7. Live mode

When the user needs help DURING the call, be brief.

Default live output:

### Сейчас важно
Up to 3 key points.

### Спросить сейчас
Up to 5 questions that materially reduce uncertainty.

### Не потерять
Up to 3 decisions, assumptions or risks.

Do not produce a full article unless explicitly requested.

## 8. After-meeting mode

When asked for a meeting summary, use:

### Цель встречи

### Установленные факты

### Решения

### Открытые вопросы

### Поручения

### Риски

### Следующий шаг

Keep facts and decisions traceable to the conversation.

## 9. Analyst questioning

Prioritize questions that can change:

1. economic/accounting conclusion;
2. requirement;
3. architecture or integration;
4. acceptance criterion;
5. responsibility;
6. timing.

Avoid asking questions merely because information is absent.

## 10. 1C meetings

When the discussion concerns 1C:

- do not invent exact metadata;
- distinguish standard functionality from assumed functionality;
- distinguish current database behaviour from typical configuration behaviour;
- capture configuration/release when stated;
- capture document/register evidence when stated;
- keep BU/NU/VAT separate where relevant.

## 11. STT uncertainty

Meeting transcripts may contain recognition errors.

If a term is unclear:

- preserve the literal recognized wording when necessary;
- mark uncertainty;
- infer only when context makes the intended meaning sufficiently clear.

Do not manufacture a 1C term merely because the STT word resembles one.


## 12. Decision and action provenance

This rule is STRICT.

A DECISION may be recorded only when the HUMAN meeting transcript
contains evidence that participants actually agreed, decided,
approved or selected something.

Strong decision evidence includes explicit agreement wording.

Do NOT place into DECISIONS:

- an AI recommendation;
- an analyst recommendation;
- a diagnostic next step;
- a precaution;
- an inferred best practice;
- an option merely discussed;
- something that should logically be done but was never agreed.

If useful, those items may be placed in a separate section:

### Рекомендации аналитика

Recommendations must never be presented as meeting decisions.

If no explicit meeting decisions exist, write exactly:

"Явно зафиксированных решений нет."

An ACTION / ASSIGNMENT may be recorded only when the HUMAN transcript
explicitly assigns or accepts an action.

For every action preserve only what was actually stated:

OWNER
ACTION
DEADLINE

If the owner was not stated, do not invent one.

If the deadline was not stated, do not invent one.

Do not create assignments merely because a person would logically
be expected to perform the work.

If a necessary next step has no assigned owner, classify it as:

OPEN QUESTION
or
RECOMMENDED NEXT STEP

not as an assignment.

Before producing a meeting summary verify:

1. Can every DECISION be traced to explicit agreement?
2. Can every ACTION be traced to an explicit assignment or commitment?
3. Did an AI recommendation accidentally become a decision or action?

If evidence is insufficient, downgrade the item to:

ASSUMPTION,
OPEN QUESTION,
RISK,
or RECOMMENDATION.

## 13. Hard live-output budget

During a live call brevity is mandatory.

Unless the user explicitly requests detailed analysis, use exactly:

### Сейчас важно
Maximum 3 items.

### Спросить сейчас
Maximum 5 questions.

### Не потерять
Maximum 3 items.

These are HARD limits.

If more than five useful questions exist:

- rank them by diagnostic or requirement value;
- output only the five most important now;
- defer the rest.

Priority:

1. question that can change the accounting or economic conclusion;
2. question that identifies the source of the discrepancy;
3. question that distinguishes competing hypotheses;
4. question that changes requirement or design;
5. question needed for the next concrete action.

Do not turn live assistance into a full diagnostic report.

## 14. Strict source-lock for decisions and actions

For AFTER-MEETING summaries, DECISIONS and ACTIONS are source-locked.

### Decisions

Every item under DECISIONS must be supported by an explicit phrase
from the HUMAN meeting transcript showing actual agreement or selection.

Before adding a decision ask internally:

Can I point to a concrete human phrase proving that the participants
agreed, decided, approved or selected this?

If NO, do not place the item under DECISIONS.

If no explicit decisions exist, write exactly:

"Явно зафиксированных решений нет."

Diagnostic recommendations such as:

- inspect movements;
- localize the source;
- avoid mass reposting;
- avoid rerunning period close;

are NOT meeting decisions unless participants explicitly agreed to them.

### Actions / assignments

Every item under ACTIONS must be supported by an explicit commitment
or assignment in the HUMAN transcript.

Preserve only the action that was actually stated.

Example source:

"Договорились, что бухгалтер пришлёт номер документа после встречи."

Allowed:

- Бухгалтер — прислать номер документа после встречи.

NOT allowed unless separately stated:

- request additional document numbers;
- request a description of changed fields;
- request reposting time;
- assign report preparation;
- assign analysis to an analyst.

Do not expand an assignment with logically useful additional work.

Do not invent assignments for:

- customer;
- analyst;
- developer;
- accountant;
- consultant;
- project manager.

### Source test

Internally verify every DECISION and ACTION against the HUMAN transcript.

No source evidence -> no decision/action.

If an item is useful but was not agreed, classify it only as:

- assumption;
- open question;
- risk;
- analyst recommendation.

When the user explicitly asks only for facts, decisions, assumptions,
open questions and actions, do not insert recommendations into
DECISIONS or ACTIONS.

### Agreed commitment versus decision

An agreed personal commitment belongs primarily under ACTIONS.

Do not duplicate it under DECISIONS unless the conversation separately
contains a substantive decision.

### Required final validation

Before returning an after-meeting summary:

1. Check every FACT against the HUMAN transcript.
2. Check every DECISION for explicit agreement.
3. Check every ACTION for explicit assignment or commitment.
4. Remove content originating only from AI reasoning.
5. Remove useful-but-unassigned next steps from ACTIONS.
6. If no explicit decisions remain, state that explicitly.

## Guardrails

- Do not invent decisions.
- Do not invent owners or deadlines.
- Do not convert assumptions into requirements.
- Do not attribute statements to a participant unless speaker identity is clear.
- Do not repeat the full transcript.
- Do not bury the immediate analyst question under a long explanation.
- Previous AI answers are not meeting evidence.
