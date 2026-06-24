# Goal — ENG-309: hard-block identity merge on DOB / SSN mismatch

Identity resolver currently merges CareStack patient records into one
`person.id` based on household signals (phone, address, accountId,
lastName) without enforcing DOB or SSN equality as a hard veto. Real-
world impact: on the Torosyan card, Eduard (DOB 1968, SSN 623-..) was
merged with Gaiane (DOB 1972, SSN 602-..), producing a single person
whose Paid + Balance summed across two distinct humans.

Goal: add a hard-block in the resolver so DOB-mismatch OR SSN-mismatch
ALWAYS refuses merge, regardless of how many soft signals overlap. Plus
an audit script to count the currently-wrong merges + (if scale permits)
a background un-merge script to split them back into distinct persons.

Frontend already exposes the multi-link expander (ENG-308). After this
ticket + ENG-310 (per-pid names), the bug becomes self-evident and the
financial summary reads true again.

Linear: ENG-309 (High)
URL: https://linear.app/fusion-dental-implants/issue/ENG-309/identity-resolution-hard-block-merge-across-different-dob-ssn
Parent: ENG-250 — Related: ENG-308 (surfaced the bug), ENG-310 (UI sibling).
