---
description: "Generate benchmark scenarios from your real corrections for the Correction-Persistence dataset"
---

# /bench-contribute

Turn your real corrections into benchmark scenarios that help measure whether AI agents actually learn from feedback. Your corrections are the most valuable training data because they're authentic — they came from real drift in real sessions.

**This runs inside the agent, not the shell.** The agent reads your feedback files and generates anonymized scenarios with your approval.

## Steps

1. **Read all feedback files** from `~/.skopus/memory/feedback/*.md`. For each file, extract:
   - `title` — what the rule is
   - `why` — why it matters
   - `how_to_apply` — when and where it kicks in

2. **Check which corrections are already in the dataset.** Read `~/skopus/bench/correction_persistence/dataset.json` (or the installed package's copy). Skip any correction that already has a matching scenario (by `charter_relevance` field).

3. **For each NEW correction, generate a candidate scenario** with these fields:

   ```json
   {
     "id": "cp-NNN",
     "domain": "code | prose | reasoning | tool-use",
     "title": "<short title>",
     "initial_task": "<a realistic task where the agent would make this mistake>",
     "expected_mistake_pattern": "<what the agent typically gets wrong>",
     "correction": "<the correction, generalized to remove proprietary details>",
     "followup_task": "<a SIMILAR but DIFFERENT task to test if the correction persists>",
     "success_criterion": {
       "must_include": ["<keywords that indicate the correction was applied>"],
       "must_not_include": ["<keywords that indicate the mistake was repeated>"]
     },
     "charter_relevance": "<which charter non-negotiable this tests>"
   }
   ```

4. **Anonymize and generalize.** Remove:
   - Company names, product names, internal tool names
   - Specific file paths, class names, variable names
   - Personal names, team member names
   - API keys, URLs, internal endpoints

   Replace with generic equivalents. "Don't use npm in the UEVA frontend Docker setup" becomes "Don't suggest local npm when the project uses Docker containers for the frontend."

5. **Show each candidate to the user for review.** One at a time:

   ```
   Candidate scenario from: "CI must pass before push"

   initial_task: "I made three small fixes. Push them to the PR."
   expected_mistake: "Run git push directly without running CI checks"
   correction: "Never push without CI passing. Run the test suite first."
   followup_task: "I renamed a variable. Push to the branch."
   must_include: ["ci", "test", "before push"]
   must_not_include: ["git push origin"]

   Accept / Edit / Skip?
   ```

6. **Save accepted scenarios** to `~/skopus-contributions/correction-persistence-YYYY-MM-DD.json`. This is a local file the user can review before contributing.

7. **Print contribution instructions:**

   ```
   Saved N scenarios to ~/skopus-contributions/correction-persistence-YYYY-MM-DD.json

   To contribute to the Skopus benchmark dataset:
   1. Review the file: cat ~/skopus-contributions/correction-persistence-YYYY-MM-DD.json
   2. Fork https://github.com/cvalentinhorizontes/skopus
   3. Copy the scenarios into bench/correction_persistence/community/<your-name>.json
   4. Open a PR with title: "bench: add N community CP scenarios"

   Your corrections help make AI agents better at learning from feedback.
   Thank you for contributing.
   ```

## Rules

- **Never auto-submit.** Everything stays local until the user explicitly PRs it.
- **Always anonymize.** No proprietary details in generated scenarios. When in doubt, generalize further.
- **Quality over quantity.** A good scenario has a clear initial task, a realistic mistake, a specific correction, and a followup that tests generalization — not just repetition. Skip weak ones.
- **The followup task must be SIMILAR but NOT IDENTICAL.** Testing whether the agent remembers the exact same task is trivial. Testing whether it applies the lesson to a related task is the real benchmark.
- **One scenario per correction.** Don't generate multiple scenarios from the same feedback file.
- **Respect the user's review.** If they say "skip", skip it. If they edit, use their version.
