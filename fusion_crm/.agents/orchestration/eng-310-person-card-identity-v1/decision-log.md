# Decision Log — ENG-310

## 2026-06-01 — Mission opened (person-card identity surfaces)

Operator asked for per-pid names in the expander + a household-link
concept: different humans under one phone/email = separate cards, but
each card shows a navigational link to the other household member(s),
financials kept separate.

**Decisions:**
1. Household key = normalized **phone/email**, NOT accountId. Verified:
   accountId=10762 is on 55,704 pids (clinic default); Torosyan mobile
   is on exactly 3 pids (the real household). Recorded in the ticket.
2. Household resolver goes through `raw_event` payload (mobile/email),
   NOT PersonIdentifier — the global UNIQUE(kind,value) means a shared
   phone lives on only ONE person after the ENG-311 split, so
   PersonIdentifier can't find siblings. Pre-flight confirms.
3. Folded 3 parts (names + PHI panel + household links) into one ENG-310
   mission per operator's cohesive framing.
4. Hybrid orchestration: 1 Haiku pre-flight → worker → 3-lens review
   (data-correctness household-key / no-PHI-leak / mocking).
5. Mission archived: eng-311-unmerge-split-persons-v1.
