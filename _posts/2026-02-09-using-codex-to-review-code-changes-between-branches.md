---
tags: ["codex", "git", "code review", "cli"]
categories: ["tooling", "git"]
title: "Using Codex to Review Code Changes Between Branches (Feature vs. Main)"
image:
  path: /assets/img/2026-02-09/main.jpg
  alt: All your code are belong to us!
---

I love code review. I also love _finishing_ code review. And if you’ve ever stared at a PR thinking “surely I’m missing something obvious”, you already know the real problem: our brains are not great at diff-scrolling for an hour straight.

This post is my practical workflow for reviewing changes **between a feature branch and `main`** with **OpenAI Codex** (the CLI + agent), without needing to open 37 browser tabs.

## Step 0: Make sure you’re diffing the right thing

When people say “compare my feature branch to main”, they usually mean:

- “Show me what my branch changes _since it diverged from `main`_ (the merge base).”

In Git, that’s the **three-dot** form:

```terminal
# From your feature branch
git fetch origin
git diff --stat origin/main...HEAD
git diff origin/main...HEAD
```

That `A...B` syntax is special:

- Git first finds the last shared commit where both branches were still the same (the **merge base**).
- Then it shows everything that changed from that shared point to `B`.

So `origin/main...HEAD` means: “Start where my branch split from `main`, then show only what my current branch added.”  
That is usually the exact view you want for branch/PR review.

## Step 1: Run a local Codex review (my favorite way)

Start Codex in your repo:

```terminal
codex
```

Then run a review preset:

1. Type:

```terminal
/review
```

2. Pick **Review against a base branch**
3. Choose your base branch (usually `main`)

Codex will figure out the merge base (against the base branch’s upstream) and review the diff. This is the closest thing I’ve found to “review my PR, but locally, right now”.

### My go-to prompt tweaks

After the preset spins up, I usually add one short message so the review isn’t generic:

- “Focus on correctness, edge cases, and missing tests.”
- “Call out any API contract changes.”
- “Flag risky refactors and backwards-incompatible behavior.”
- “List the top 5 things you’d comment on in a PR, with file paths.”

## Step 2: Ask Codex to summarize the change like a PR description

This sounds silly, but it catches problems fast because it forces the reviewer (human or AI) to build a coherent mental model.

Ask for:

- A 5–10 bullet summary (“what changed”)
- A “why” hypothesis (“what this is trying to achieve”)
- A checklist of tests to run
- A list of “areas of risk”

If the summary doesn’t match your intent, the diff is probably confusing… which means your teammates are about to have a bad time too.

## Step 3: One-shot mode with `codex exec` (nice for scripts)

If you want a “review pass” without an interactive session, `codex exec` can run an agentic task from your shell.

Example idea:

```terminal
codex exec "Compare my current branch with origin/main and list: (1) likely bugs, (2) missing tests, (3) backwards-incompatible changes. Use file paths."
```

I still prefer `/review` for deeper diffs, but `codex exec` is great for quick sanity checks (or when you’re wiring this into a local script).

## Bonus: Reviewing GitHub PRs with Codex

If your team lives in GitHub PRs, you can also use Codex there: comment with a mention (for example, `@codex review`) and ask for what you want (security pass, test gaps, style, etc.). It’s a different workflow than local `/review`, but it’s convenient when the conversation is already in the PR.

## Gotchas (aka “why does this review feel wrong?”)

### 1) Two-dot vs three-dot confusion

- `main..feature` is “commits reachable from `feature` but not `main`” (fine for some things).
- `main...feature` is “diff from merge base to `feature`” (usually what you want for branch review).

If you’re ever unsure, run both `--stat` outputs and see which one matches the changes you actually made.

### 2) Your base branch doesn’t track an upstream

Codex’s base-branch review relies on the base branch’s upstream when computing the merge base. If your `main` isn’t tracking `origin/main`, fix that first:

```terminal
git branch -u origin/main main
```

### 3) Huge diffs produce huge reviews

If the diff is massive, ask Codex to review in passes:

- “First: high-level architecture + public APIs.”
- “Second: correctness and edge cases.”
- “Third: tests, docs, and naming.”

You can also scope it: “Only review `src/`” or “Ignore formatting-only changes.”

## Wrap-up

My “default” flow is:

1. `git diff origin/main...HEAD` to sanity-check the size and shape of the change
2. `codex` → `/review` → “Review against a base branch”
3. Ask for a PR-style summary + test checklist

It’s fast, it’s local, and it catches a shocking number of “oops” moments before anyone else sees them.

## References

- OpenAI Codex CLI docs (review presets, `/review`, `codex exec`): https://developers.openai.com/codex/cli
- Git docs for `git diff` (including the `A...B` merge-base form): https://git-scm.com/docs/git-diff
- OpenAI Help Center (Codex in GitHub, `@codex` usage): https://help.openai.com/en/collections/10677170-codex
