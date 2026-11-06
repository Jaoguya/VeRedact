# VeRedact-PQ — instructions for agents

Team (GitHub): **jaoguya** (repo owner, AWS approver), **Ppdfd**, **yewza101**, **Rangsimann** (joining). You work
for one of them, your **owner**; ask for their GitHub username once if you do not know it.

Read before working: `README.md` (latest full-run results, caveats, how to check them), `Other/docs/experiments.md`
(experiment rules), `Other/docs/paper-conformance.md` (where code and manuscript differ). Open work: GitHub issues.

## Guardrails

- **AWS**: any action that creates, starts, stops, changes or deletes something on AWS runs only after
  **jaoguya** has written a yes for that exact action as a comment on its issue. Check it with
  `gh issue view <n> --comments`: the comment's author is `jaoguya` and it names the action. One yes covers one
  action. Without it, add the label `needs-aws` and ask jaoguya on the issue.
- **Honest numbers**: report and plot only values read from full-run results files (`metrics.json`). Smoke runs
  check code paths; their numbers are never results.
- **Fair baselines**: baselines follow their papers. A PR that changes
  `Benchmark/src/veredact_bench/methods/baselines/` cites the paper section it follows.
- **Manuscript** (`Overleaf/`): change it through a PR, approved by a teammate other than the author of the change.

## Working an issue

GitHub issues and PRs are the team's only channel. Start the first line of every comment, issue and PR you write
with `🤖 <agent> (for <owner>):`. Before each GitHub post that changes an issue's state (claim, blocked, done, next),
show your owner what you will post and post it after they agree.

1. **Propose**: list open, unassigned issues (`gh issue list --search "no:assignee -label:blocked"`), pick one
   that fits, and give your owner the issue number and a short plan. Done when your owner says yes.
2. **Claim**: `gh issue edit <n> --add-assignee <owner> --add-label in-progress`, then comment
   `picked up: <plan>`. Done when the issue shows the assignee, the label and the comment.
3. **Work** on branch `<n>-<short-slug>` from `main`; run `make test lint` in `Benchmark/` before pushing.
4. **Blocked**: add the label `blocked` and comment with four parts: *What I did*, *What happened* (error or log in
   a `<details>` block), *What I tried*, *Question*. @mention who can answer (your owner by default). Remove the
   label when unblocked.
5. **Finish**: open a PR whose body contains `Closes #<n>` and fills the PR template; when CI is green, comment
   `done: PR #<m>` on the issue and remove `in-progress`. Then go back to step 1.

A PR merges into `main` after one approval from a teammate and green CI.

## Results releases

Each full run gets a GitHub Release tagged `run-YYYY-MM-DD` on the commit that produced it. Attached: the
`experiment-reps` aggregates (`metrics.json`, `config_resolved.yaml`, `run_info.json`), per-run `metrics.json`,
and the coverage/exit logs; the notes give commit, image, dates, coverage and caveats. Figures and tables stay
committed in `Result/` and `Overleaf/tables/`; the raw `Benchmark/results/` stays on veredact-bench.
