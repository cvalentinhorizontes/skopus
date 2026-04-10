---
name: seed-team-lead
description: Seed feedback for the team-lead profile. Unblock the team, document decisions, review critical paths.
type: feedback-seed
---

# Team Lead Seed Feedback

> 🌱 *Seeded by `skopus init`. Edit or delete — this is a starting point, not a commitment.*

## Rule: Document decisions as they're made

When making a non-trivial technical decision, write an ADR (Architecture Decision Record) or a decision doc in `docs/decisions/`. Include the decision, the rationale, the alternatives rejected, and the trade-offs accepted.

**Why:** Teams lose context when decisions are only in Slack threads or code reviews. New hires and future-you need the "why" preserved.

**How to apply:**
- ADR template: Context, Decision, Consequences, Alternatives Considered
- Link to the ADR from the relevant code comments
- Review ADRs monthly — retire stale ones, update superseded ones

## Rule: Unblocking > shipping

A team lead's job is to unblock the team. If a team member is stuck and you're shipping a feature, stop shipping and unblock them. Your individual output matters less than the team's aggregate output.

**Why:** Team lead leverage comes from force multiplication, not individual contribution. An hour unblocking 3 people is worth 3+ hours of your own work.

**How to apply:**
- Morning check: any PR waiting on review > 4 hours? Review first.
- Any Slack question unanswered > 2 hours? Answer or assign.
- Only start your own deep work after the team is unblocked.
