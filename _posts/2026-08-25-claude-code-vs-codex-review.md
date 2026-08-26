---
# SEO Target Queries:
#   Google: "claude code vs codex", "codex exec code review", "ai code review cli"
#   Bing:   "claude code vs codex", "claude code review pull request", "codex cli review"
tags: ["ai", "codex", "claude-code", "code-review", "developer-tools"]
categories: ["ai", "tooling"]
title: "Claude Code vs Codex Review: Both Caught My Bugs"
image:
  path: /assets/img/2026-08-25/main.jpg
  alt: Two inspectors handed the same envelope, both finding the same two problems.
published: false
---

I put two bugs into a repository on purpose. One deleted `.AsNoTracking()` from a bulk CSV export. The other renamed an Angular `@Output()` from `sortChanged` to `sortChange` and left all four consumer templates binding the old name.

Then I handed the same one-sentence prompt to `codex exec` and to `claude -p`, and watched.

I went in expecting a clean result: the second bug is invisible in the diff, so whichever tool reads only the diff should miss it. That is the story I have read a dozen times about static review scripts versus agents.

Both tools found both bugs. The interesting part turned out to be somewhere else entirely.

## The repository

Not a toy. A real Angular 22 app and a real .NET 10 library, both of which compile:

```bash
npx @angular/cli@22 new storefront --style=scss --ssr=false --defaults
dotnet new classlib -o backend
dotnet add package Microsoft.EntityFrameworkCore --version 10.0.0
```

The backend has an export service whose own doc comment tells you the scale:

```csharp
/// <summary>
/// Streams every order in a date range straight to a CSV writer.
/// Typical export covers a full year - hundreds of thousands of rows.
/// </summary>
public Task<List<Order>> GetOrdersForExportAsync(DateTime from, DateTime to, CancellationToken ct)
{
    return _db.Orders
        .AsNoTracking()
        .Where(o => o.PlacedAt >= from && o.PlacedAt < to)
        .OrderBy(o => o.PlacedAt)
        .ToListAsync(ct);
}
```

The frontend has one shared table component with an output, and four pages consuming it:

```typescript
@Output() sortChanged = new EventEmitter<SortEvent>();
```

```html
<app-data-table [columns]="columns" [rows]="rows" (sortChanged)="onSort($event)" />
```

`main` builds clean on both sides. Then the branch `feature/table-cleanup` deletes `.AsNoTracking()`, renames the output, and adds a little innocent noise so the diff is not a two-line giveaway.

## Why I expected one of them to fail

The whole diff is fifty lines:

```bash
git diff main...HEAD | wc -l
```

```text
50
```

And here is every place the old event name appears **inside that diff**:

```bash
git diff main...HEAD | grep -n 'sortChanged'
```

```text
35:-  @Output() sortChanged = new EventEmitter<SortEvent>();
43:-    this.sortChanged.emit({ column, direction: this.direction });
```

Two lines, both deletions, both in the component that was supposed to change. Meanwhile the actual damage sits in four files that the diff never mentions:

```bash
grep -rn 'sortChanged' --include=*.html --include=*.ts . | grep -v node_modules
```

```text
storefront/src/app/pages/reports.component.html:5:  (sortChanged)="onSort($event)"
storefront/src/app/pages/orders.component.html:5:  (sortChanged)="onSort($event)"
storefront/src/app/pages/admin.component.html:5:  (sortChanged)="onSort($event)"
storefront/src/app/pages/dashboard.component.html:5:  (sortChanged)="onSort($event)"
```

**Anything reviewing only the diff cannot possibly find this.** The information is not there. You have to leave the diff and go look at the repository, which is exactly the thing a single-shot prompt cannot do.

For the record, the bug is real and the build catches it:

```bash
cd storefront && npx ng build
```

```text
Application bundle generation failed. [1.791 seconds]
✘ [ERROR] TS2345: Argument of type 'Event' is not assignable to parameter of type 'SortEvent'.
✘ [ERROR] TS2345: Argument of type 'Event' is not assignable to parameter of type 'SortEvent'.
✘ [ERROR] TS2345: Argument of type 'Event' is not assignable to parameter of type 'SortEvent'.
✘ [ERROR] TS2345: Argument of type 'Event' is not assignable to parameter of type 'SortEvent'.
```

Four errors, one per page.

## The identical prompt

Both tools got this, word for word, and nothing else:

```text
Review the changes on this branch against main. Report any bugs, regressions, or breaking changes you find, with file and line references.
```

The versions in play:

```bash
codex --version
claude --version
```

```text
codex-cli 0.149.1
claude@2.1.245
```

## Round 1: Codex

```bash
codex exec -C "$REPO" -s workspace-write "$(cat prompt.txt)"
```

It finished in **60 seconds** and ran seven shell commands to get there. The interesting ones, straight out of the transcript:

```text
git status --short && git branch --show-current && git diff --stat main...HEAD && git diff --name-only main...HEAD

rg -n "sortChanged|sortChange|app-data-table|GetOrdersForExportAsync|CountInRangeAsync|ExportService|OrderLookupService|describeSort" .
   --glob '!**/node_modules/**' --glob '!**/bin/**' --glob '!**/obj/**'

dotnet build backend/backend.csproj --no-restore

npm run build -- --configuration production
```

That is not a static diff reviewer. It read the diff, grepped the whole repository for the renamed symbol, then built both projects to check its own hypothesis. Its report:

```text
Found two regressions:

- **High — Frontend no longer builds.** table.component.ts:36 renames the output from
  `sortChanged` to `sortChange`, but all four consumers still bind `(sortChanged)`, for
  example dashboard.component.html:5. Production compilation fails with `TS2345` in
  dashboard, admin, orders, and reports. Either retain the old output name or update
  every consumer.

- **Medium — Large exports now unnecessarily track every order.** ExportService.cs:30
  removes `AsNoTracking()` from a read-only query documented as returning hundreds of
  thousands of rows. EF Core will retain tracking entries and snapshots for the entire
  result set, increasing memory and change-detection costs and potentially causing
  severe slowdown or out-of-memory failures. Restore `AsNoTracking()`.

Verification: `dotnet build` succeeds; `ng build --configuration production` fails with
the four output-binding errors above.

tokens used
14,600
```

Both bugs, correct severities, correct file and line references, and a verification line at the end. So much for my premise.

## Round 2: Claude Code

```bash
claude -p "$(cat prompt.txt)" \
  --allowedTools "Read" "Grep" "Glob" "Bash(git:*)" "Bash(npx ng build)" "Bash(dotnet build:*)"
```

**115 seconds**, and the same two findings. What it added was explanation of the *mechanism*:

```text
Because `(sortChanged)` no longer matches an output, Angular falls back to a DOM event
binding and `$event` narrows to `Event`, so `ng build` fails four times
```

That sentence is the actual reason for a `TS2345` that otherwise looks unrelated to a rename. It also volunteered a third, smaller finding that Codex did not mention:

```text
## 3. Minor: both additions are unused

- `describeSort` (table.component.ts:46) has no callers.
- `CountInRangeAsync` (OrderLookupService.cs:14) has no callers, and duplicates the
  `>= from && < to` range predicate from ExportService.cs:31 rather than sharing it.

Not bugs, but both are new dead code in a commit titled "Clean up", so flagging in case
they were meant to be wired into something.
```

That was my innocent noise, correctly identified as dead code.

And it drew a line where its evidence ran out, which I liked more than anything else in either report:

```text
There's a secondary correctness angle if the context is ever longer-lived than
per-request: with tracking on, a second export in the same context returns
identity-mapped instances instead of fresh DB values. I can't confirm the DI lifetime —
there's no `Program.cs` or DI registration in the repo — so treat that as conditional on
how `StorefrontContext` is scoped.
```

Correct. There is no `Program.cs`. It noticed, said so, and flagged its own conclusion as conditional.

## Round 3: the same run again

Agents are not deterministic, so a single run of each proves very little. I ran Claude Code a second time on the same commit, this time asking for machine-readable output so I could see what it cost:

```bash
claude -p "$(cat prompt.txt)" --allowedTools ... --output-format json
```

```text
duration_ms : 124014
duration_api_ms : 113283
num_turns : 23
total_cost_usd : 0.5148375
usage: {'input_tokens': 24, 'cache_creation_input_tokens': 12191,
        'cache_read_input_tokens': 432665, 'output_tokens': 7059}
```

Same two bugs again, plus one observation the first run had not made:

```text
Note the strict-template check is the only thing catching this. Had the handlers been
typed loosely (e.g. `onSort(event: any)`), this would have compiled clean and silently
dead-ended every sort interaction in the app - the listener would attach to a DOM event
that is never dispatched.
```

That is a genuinely useful warning, and it is not in the diff, not in the build output, and not in run one. Two runs of the same agent on the same commit produced overlapping but not identical reviews.

## The scoreboard

| | Codex | Claude Code |
| --- | --- | --- |
| Bug 1: `AsNoTracking()` removed | found | found |
| Bug 2: renamed output, 4 broken callers | found | found |
| Dead code in the "cleanup" commit | not mentioned | found |
| Ran the builds to verify | yes | yes |
| Wall clock | 60 s | 115 s and 124 s |
| Self-reported cost | 14,600 tokens | $0.51, 7,059 output tokens, 23 turns |

Two caveats before anyone quotes that table. The cost numbers are not comparable: Codex reports a single token count, Claude Code reports a breakdown dominated by cache reads, and I did not normalise them. And the two runs had different permission setups. Codex ran under its `workspace-write` sandbox; Claude Code ran with an explicit allowlist of read tools plus `git`, `npx ng build` and `dotnet build`. Neither was given a free hand.

## What I actually learned

The comparison I set out to run does not exist any more. "Static diff prompt versus autonomous agent" was a real distinction, and today both of these tools sit firmly on the agent side. Both left the diff. Both grepped the repository. Both ran the build. The planted bug that was supposed to separate them separated nothing.

What genuinely differed was **temperament**. Codex was fast and stopped as soon as it had two confirmed regressions. Claude Code was roughly twice as slow, explained the compiler mechanism, flagged the dead code, and marked one conclusion as unverifiable because a file it needed was missing.

Neither of those is better in the abstract. Before a commit, I want the fast one. Before a pull request lands on somebody else's afternoon, I want the one that tells me what it could not check.

## Summary

* **A diff-only review physically cannot catch a renamed symbol**, because the broken call sites are not in the diff. I confirmed it: two matching lines in fifty, both deletions.
* **Both CLIs found both planted bugs**, with correct file and line references, and both ran the builds to confirm.
* **Codex was about twice as fast** and stopped at the two confirmed regressions.
* **Claude Code volunteered more**: the mechanism behind the error, the dead code, and an explicit note about what it could not verify.
* **Two runs of the same agent gave different reviews.** Overlapping, both correct, not identical. Treat one run as a sample, not a verdict.
* **Neither tool is a build.** Both of them found bug 2 the same way you would: by grepping for the old name and running `ng build`.

Friendly closing tip: if you want to know whether an AI review is worth its wall clock in your repository, do what I did here. Plant a bug you already understand, one that a diff cannot show, and see whether the tool goes looking. It takes an afternoon and it tells you far more than any comparison table someone else wrote.
