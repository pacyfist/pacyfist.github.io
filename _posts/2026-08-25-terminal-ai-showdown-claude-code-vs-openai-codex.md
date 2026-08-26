---
# SEO Target Queries:
#   Google: "claude code vs codex", "claude code cli", "claude code vs cursor"
#   Bing:   "claude code vs codex", "claude code vs github copilot"
tags: ["ai", "codex", "claude-code", "git", "developer-tools"]
categories: ["ai", "tooling"]
title: "Claude Code vs OpenAI Codex: Which Terminal AI Agent Reviews PRs Better?"
published: false
---

Back in February, I wrote about [using OpenAI Codex to review code changes between branches](https://www.pacyfist.dev/posts/using-codex-to-review-code-changes-between-branches/). The workflow was simple and effective: dump a `git diff` into a python script, feed it to the model with a structured review prompt, and get a markdown summary of bugs and risks before opening a PR.

That script saved me from shipping a dozen stupid mistakes over the spring.

Recently, Anthropic launched **Claude Code**, an agentic CLI tool designed to run directly inside your terminal, execute bash commands, navigate codebases, and interact with git.

Naturally, I wanted to see if an autonomous terminal agent beats my lightweight Codex script at reviewing real pull requests. I took a 400-line diff spanning an Angular frontend and a C# backend, containing one subtle breaking change and one performance regression, and pitted them against each other.

Here is what happened.

## The Two Contenders

First, let's understand the architectural difference between the two approaches:

### Contender A: The Static Prompt (OpenAI Codex Script)
* **Model:** GPT-4o / Codex-style completion.
* **Mechanism:** Single-shot prompt. You pipe `git diff main...feature-branch` into the script. The script bundles the diff with instructions ("Find logic bugs, security holes, and API breaks") and prints the analysis.
* **Cost / Latency:** Fast (~5 seconds), predictable, uses minimal tokens.
* **Limitation:** The LLM can only see the lines that changed in the diff. It has zero knowledge of untouched files, call sites, or database schemas unless you manually paste them in.

### Contender B: The Autonomous Agent (Claude Code CLI)
* **Model:** Claude 3.7 Sonnet / Claude 3.5 Sonnet.
* **Mechanism:** Agentic loop. Claude Code runs inside your repository. It doesn't just read the diff—it has access to tools: `grep`, `file_search`, `bash` execution, and Model Context Protocol (MCP) servers.
* **Cost / Latency:** Slower (30–90 seconds), higher token usage.
* **Superpower:** If a method signature changed in the diff, Claude Code can search the entire repository to check if callers were updated, and even run `dotnet test` or `npm test` to verify its hypothesis.

## The Test: Two Planted Bugs

I prepared a PR with two deliberate issues:

1. **Bug 1 (C# Backend):** Changed an EF Core query from `AsNoTracking()` to tracking inside an endpoint that processes large bulk exports, introducing a memory spike and lock contention.
2. **Bug 2 (Angular Frontend):** Renamed an `@Output()` event in a shared table component from `sortChanged` to `sortChange`. The component diff looked totally benign—the bug was that 4 consuming pages still listened to `(sortChanged)`.

## Round 1: Catching Bug 1 (The EF Core Tracking Regression)

* **Codex Script:** Caught it instantly. Because the change was right there in the diff (`.AsNoTracking()` removed), the static prompt flagged:
  > *"Warning: Removing AsNoTracking() on line 42 will cause EF Core change tracker overhead for large result sets."*
* **Claude Code:** Also caught it, and went one step further. It noted:
  > *"Removing AsNoTracking() here causes DbContext entity tracking. In `ExportService.cs:L88`, this result is passed into a streaming CSV writer where tracking is completely redundant."*

**Winner:** Tie. Both easily caught the localized bug.

## Round 2: Catching Bug 2 (The Multi-File Caller Breakage)

This is where the difference became glaring.

* **Codex Script:** Completely missed it. Why? Because from the diff alone, renaming an `@Output()` property in `table.component.ts` looks like clean code. The diff contained no errors. The breakages existed in `dashboard.component.html` and `reports.component.html`, which were untouched and therefore not part of the diff.
* **Claude Code:** When asked to review the branch diff (`claude "review the changes against main"`), Claude Code:
  1. Ran `git diff main` to see what changed.
  2. Identified that `table.component.ts` changed an `@Output` property.
  3. Ran a `grep` across the project for usages of the old event name `sortChanged`.
  4. Found 4 references in existing HTML templates that were not updated!
  5. Ran `ng build` in the background, which confirmed the template type-checking errors.

Its report:
> *"🚨 Breaking Change in TableComponent: You renamed `sortChanged` to `sortChange`, but `dashboard.component.html:L24` and `reports.component.html:L56` are still binding to `(sortChanged)`. This will silently break sorting on those pages."*

That single catch saved 20 minutes of debugging in staging.

## Where Codex Still Wins

While Claude Code has the intelligence advantage of full repo context, it's not strictly better in every scenario:

1. **Speed & Focus:** If you just made a quick 10-line commit and want an instantaneous sanity check, piping to a script takes 3 seconds. Waiting for an agent to explore tools takes noticeably longer.
2. **Deterministic Guardrails:** With a script, you know exactly what is executing. You never have to worry about an agent accidentally running a slow build command or modifying a file when you only asked for a review.

## My Current Daily Workflow

I haven't thrown away my Codex script, but my workflow has shifted:

* **Pre-commit sanity check (Local):** Fast static diff script. Catches obvious typos, forgotten `console.log` statements, and careless null checks in seconds.
* **Pre-PR architecture review (Branch):** **Claude Code CLI**. I run:
  ```bash
  claude "Review the diff against main. Verify whether any renamed symbols broke untouched callers, and run the test suite to confirm."
  ```

Having an agent that doesn't just read code, but *actively verifies its claims by grepping callers and running tests*, turns an AI review from a polite suggestion box into an actual pair programmer.
