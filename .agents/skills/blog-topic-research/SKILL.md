---
name: blog-topic-research
description: Research topics for a new blog post.
---

# Blog Topic Research

Find topics for **pacyfist.dev** that people are actively searching for, that the
current top results serve badly, and that Filip can write from real hands-on
experience.

The output is a **ranked shortlist of 5-8 candidates**, not a single pick. Filip
chooses; your job is to make the tradeoffs legible.

## Why this needs a method

Two traps sit on either side of this task.

The first is searching "top software development trends 2026". That returns SEO
listicles written by content farms describing what _other listicles_ say is
trending. It is not demand data. Skip that genre entirely.

The second is the opposite error: assuming that because you have no paid keyword
tool, demand can't be measured at all, and reasoning purely from release
calendars. You can do better than that. Google and Bing both expose their
autocomplete suggestions over unauthenticated HTTP, and engines only suggest
completions they actually observe people typing. That is real demand data from
the two engines Filip cares about, and `scripts/suggest.py` pulls it.

So: **measure demand where you can, infer it only where you can't, and always
say which you did.**

## The blog you're writing for

pacyfist.dev — Filip Franik. Jekyll + Chirpy.

Filip is a pragmatic, hands-on developer running an Arch Linux (Omarchy / Hyprland) workstation. He works heavily with C# and TypeScript, but blogs across a wide, curious developer workbench.

**Topic Pillars (all first-class fit):**

1. **.NET, C# & Data Architecture:** C#, .NET runtime, ASP.NET Core, EF Core, SQL Server, performance/benchmarking, caching (HybridCache), database internals/indexing, modern APIs (OpenAPI, Scalar, gRPC).
2. **Frontend & Modern Web:** TypeScript, Angular (Signals, modern reactive state), modern styling & UI (Tailwind CSS, DaisyUI), frontend tooling (Vite, Vitest, Bun/Node), browser platform APIs.
3. **AI Tooling & Agentic Workflows:** Practical AI dev tooling, AI coding agents and CLI runners (Antigravity, Codex, Claude Code, Cursor), Model Context Protocol (MCP) servers and tool design, local LLMs (Ollama), embeddings, text-to-SQL, real developer agent workflows.
4. **Linux, Systems & Developer Ergonomics:** Arch Linux / Omarchy, Hyprland / Wayland, shell & terminal ergonomics (tmux, Neovim, zsh, starship, CLI utilities), hardware/disk/filesystem rescue and recovery (ddrescue, ntfs, btrfs), developer workstation efficiency.
5. **Game Development & Graphics:** Flax Engine (C#/C++ game engine), Three.js / WebGL / WebGPU, shader development, 3D graphics on web or native.
6. **DevOps, Containers & Dev Environments:** Docker, CI/CD, local dev setups, self-hosting, developer networking and containerization.
7. **Wildcard & Hands-On Curiosity ("Anything Interesting"):** Technical rabbit holes, unusual debugging adventures, hardware/firmware tinkering, reverse-engineering, after-hours experiments that yield a real story and a reproducible lesson.

**Voice:** hands-on, after-hours side project, step-by-step. Posts open with a
personal story about hitting the problem for real. Read `_posts/` at the start of
every run rather than trusting this list — the catalog moves.

**Search engines that matter:** Google _and_ Bing.
- **Google** is the global baseline for all developer queries (Linux, AI tooling, web, game dev, DevOps, languages).
- **Bing** over-indexes Microsoft-stack and Microsoft-docs-adjacent queries, so a .NET/C#/SQL Server topic gets an extra Bing traffic boost.
- `suggest.py` returns both engines separately so you can see where demand lives.

## Step 1 — Read the catalog

Read `_posts/`. You need four things from it:

1. **What's already covered** — don't propose a topic Filip has written.
2. **Sequel opportunities** — a post with a natural next chapter is worth more
   than a cold-start topic, because it inherits authority and internal links.
3. **Posts that may have gone stale.** If a post covers version N of something
   now on version N+2, it is probably still ranking for queries about the newer
   version. That's Step 5's "refresh in place" case, and it is often the highest
   value-per-hour work available. Search for the _newer_ version's query and see
   if Filip's own post comes back.
4. **What Filip can plausibly have run himself.**

That last one is a hard constraint. The `blog-post-writer` skill requires every
post to open with a story about hitting the problem in a real side project, and
every console command to be followed by its actual output. A topic Filip cannot
install and run on his own machine cannot be written in this blog's voice. Drop
such topics however good the demand looks — and say in the writeup that you did.

## Step 2 — Generate candidates

Aim for **12-16 raw candidates** before filtering to the shortlist. Actively sample
across at least 3-4 distinct pillars so the raw pool is diverse. Look where demand
is _about to_ arrive as well as where it already is:

- **Release calendars & previews (1-4 months before GA):**
  - *.NET / C# / DB:* .NET previews, C# language feature status, EF Core "what's new", SQL Server release notes.
  - *Frontend / Web:* Angular releases, TypeScript upcoming features, Vite/Vitest major updates, Tailwind/CSS standards.
  - *AI / Agents:* MCP specification additions, agent SDK updates (Antigravity, Claude Code, Cursor), local inference engines (Ollama, llama.cpp).
  - *Linux / Workstation:* Linux kernel / systemd updates, Hyprland / Wayland releases, Omarchy/Arch package changes.
  - *Game Dev:* Flax Engine releases, Three.js releases.
- **Recently-shipped features still marked experimental or preview** — thin docs
  by definition, which is where the gap lives.
- **Breaking changes and upgrade pain.** "X broke when I upgraded to Y", missing flags,
  migration paths (e.g. Karma to Vitest, OpenAPI Swashbuckle to Microsoft OpenAPI).
  Error strings are the easiest queries for a small blog to rank for, because vendor docs rarely target them directly.
- **Developer-side spikes:** Hacker News top-of-week, r/dotnet, r/Angular2, r/linux,
  r/unixporn, r/LocalLLaMA, r/gamedev, Stack Overflow trending tags, and GitHub issues
  of fast-moving tools. A flood of "this broke after the update" issues is demand
  arriving before anyone has written the answer.

## Step 3 — Measure demand

Run the bundled script on your candidates:

```bash
python3 .agents/skills/blog-topic-research/scripts/suggest.py "candidate term" "another"
```

Add `--deep` on the two or three most promising to expand with a-z and question
prefixes. That surfaces the specific phrasings people use, which matters for
Step 5.

Reading the output:

| What you see                      | What it means                                                         |
| --------------------------------- | --------------------------------------------------------------------- |
| Full tree on both engines         | Real, sustained demand. Best case.                                    |
| Rich on Google, thin on Bing      | Real demand, weaker Bing upside — note it.                            |
| Mostly "release date" / "when is" | Anticipation traffic. Converts poorly; people are curious, not stuck. |
| Only the bare echo, or nothing    | No demand _at this phrasing_.                                         |

That last row is the subtle one, and it is a keyword-targeting finding, not a
verdict on the topic. Suggestions have a popularity threshold; falling below it
means "not enough people type this exact string," not "nobody cares." So when a
precise technical phrasing returns nothing but its parent term returns a full
tree, the topic is fine and **your title is wrong** — write for the head term
people actually type, and put the precise phrasing in a heading inside the post.
Chasing a zero-suggestion long-tail string because it sounds like the real
subject is how good topics get published to silence.

Fold the exact suggested phrasings into the title suggestions you make. They are
the queries, verbatim.

## Step 4 — Verify competition

For every candidate reaching the shortlist, do the work — don't score from vibes.

1. **Search it and look at _who_ ranks.** Vendor docs plus well-known ecosystem
   blogs is a hard field. Content farms and thin posts is an open field.
2. **Read two or three of the top-ranking posts.** You are looking above all for
   **decay**: content written against an earlier preview, an older major version,
   or a since-changed default. A first page full of advice that is now factually
   wrong is the best possible signal — their ranking proves the demand, and you
   beat them on accuracy alone.
3. **Check the primary source** — vendor release notes or docs — for the current
   state. This is where you find the fact that invalidates the incumbents: a flag
   that used to be required, a default that flipped, an API renamed between
   previews.
4. **Name the angle.** If you can't say in one sentence what this post says that
   the top result doesn't, the candidate is weak regardless of demand.

Run searches for different candidates in parallel; this step is the bulk of the
work and it is embarrassingly parallel.

Be willing to reverse yourself here. Finding that a promising candidate's
incumbents have already corrected themselves is a real result — report it as a
rejection with the evidence rather than quietly softening the score.

## Step 5 — Score and rank

Four axes, 1-5. Scores sort the list; the notes carry the information.

| Axis       | 5 means                                                                             | 1 means                                                  |
| ---------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **Demand** | Full autocomplete tree on both engines, plus a release or breakage event driving it | Nothing on either engine at any phrasing                 |
| **Gap**    | Top results are stale, wrong, or thin                                               | Vendor docs plus strong ecosystem blogs own it           |
| **Fit**    | High hands-on credibility; Filip can run and lab-test it on his workstation tonight | Cannot be reproduced locally on Filip's machine          |
| **Angle**  | A specific, non-obvious claim only this post makes                                  | "Here's what's new in X", same as everyone else          |

Ground Demand in the `suggest.py` output wherever you have it, and say so. Where
you're reasoning from a release calendar instead, mark it as inferred.

Override the arithmetic when judgment says so: a candidate scoring 1 on Fit is
disqualified regardless of its total, because it cannot be written in this
blog's voice.

Note the **Bing bonus** explicitly rather than hiding it in a score — say which
candidates get a second search engine working for them.

**Shortlist Diversity Requirement:**
Unless Filip explicitly asks for a narrow topic focus (e.g. "give me .NET ideas"), the final 5-8 candidate shortlist **must include topics from at least 2-3 different pillars**. Avoid single-stack monoculture where all candidates belong to just .NET or just Angular.

**A shortlist entry may be "refresh an existing post" rather than a new one.**
If Step 1 found a post already ranking for a newer version's query, updating it
in place keeps the URL and its accumulated authority, usually costs a fraction of
a new post, and avoids competing with yourself for the same keyword. Rank it
alongside the new-post candidates and be honest that its Angle score is low —
low Angle and near-zero cost is often a better trade than the totals suggest.

## Step 6 — Deliver

Lead with the ranked table, including the Pillar column so variety is legible at a glance:

```markdown
## Shortlist

| #   | Topic | Pillar | Demand | Gap | Fit | Angle | Total | Note                     |
| --- | ----- | ------ | ------ | --- | --- | ----- | ----- | ------------------------ |
| 1   | ...   | ...    | 5      | 5   | 5   | 4     | 19    | one line on why it's top |

## The top three, expanded

### 1. [Topic]

**Pillar:** [Topic Pillar]
**Why now:** timing and release-curve reasoning, with dates.
**Demand evidence:** the actual suggestion strings, per engine.
**What's ranking, and why it loses:** who's on page one and what's wrong with it.
**The angle:** the one sentence this post says that they don't.
**Sequel to:** existing post it builds on, if any.
**Risk:** what would make this a bad call.

## Skipped, and why

Candidates rejected, with reasons — saturated, no demand at any phrasing,
outside the stack, can't be reproduced locally, or incumbents turned out fine.

## Confidence

Separate what you measured (autocomplete trees, what actually ranks, primary-source
facts) from what you inferred (where demand goes next). Both belong; conflating
them doesn't.
```

Close by asking which one to take to `blog-post-writer`.

## Traps

- **Don't grade on interestingness alone.** A topic being cool is not demand. Every
  ranking must survive "would someone type this into a search box while stuck?"
- **Don't fall into single-stack tunnel vision.** Do not present a shortlist where every
  single item is from the same technology stack unless requested. A strong shortlist offers
  Filip diverse directions for his next post.
- **Avoid generic AI hype, embrace concrete developer tooling.** Do not propose speculative
  "How AI will change coding" thinkpieces. Propose concrete, reproducible developer workbench
  topics: custom MCP servers, agentic terminal workflows, local Ollama embedding pipelines,
  or hands-on agent benchmarking.
- **Don't propose what you can't verify.** If research turns up nothing concrete
  about a candidate's current state, drop it rather than hedging in the writeup.
- **Don't inflate every score.** A shortlist that's all 4s and 5s is useless for
  choosing. Real candidates have real weaknesses; name them.
- **Don't skip `suggest.py` because the topic seems obviously popular.** The
  cases where it changes your mind — a beloved technology with no search
  footprint, or a boring one with a huge tree — are exactly the cases where your
  intuition was going to cost Filip a weekend.
