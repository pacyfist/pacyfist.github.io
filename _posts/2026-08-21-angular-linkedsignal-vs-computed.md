---
# SEO Target Queries:
#   Google: "angular linkedsignal vs computed", "angular linkedsignal", "angular linkedsignal previous"
#   Bing:   "angular linked signal", "linkedsignal vs effect", "how to use linkedsignal angular"
tags: ["typescript", "angular", "signals", "linkedsignal", "reactivity"]
categories: ["typescript", "angular"]
title: "Angular linkedSignal vs computed: The Reset You Missed"
image:
  path: /assets/img/2026-08-21/main.jpg
  alt: A list that helpfully unselects your choice every time it refreshes.
published: false
---

There are already good explanations of what `linkedSignal` *is*, so this post starts where they stop. I pointed one at a list, selected item #3, refreshed the list with the exact same three items, and watched the selection jump back to item #1.

Nothing had changed. The array was new, the contents were identical, and my selection was gone anyway.

That felt worth measuring properly, so I built a lab and wrote down what every case actually does. Every log line below came out of that lab, and one of the results changed how I write `linkedSignal` entirely.

## The lab

A default Angular 22 workspace, which now ships Vitest as the test runner:

```bash
npx @angular/cli@22 new signalslab --style=scss --ssr=false --defaults
npx ng version
```

```text
Angular CLI       : 22.1.6
Angular           : 22.1.3
Node.js           : 26.5.0
Package Manager   : npm 11.17.0
Operating System  : linux x64
```

The runner matters for reading the output below, so here is the relevant row of the
package table that `ng version` prints underneath:

```text
│ vitest                    │ 4.1.11            │ ^4.0.8            │
```

Every experiment prints one line, so the test transcript is the evidence:

```typescript
interface Item { id: number; name: string; }

const item = (id: number): Item => ({ id, name: `Item #${id}` });

function probe(label: string, payload: unknown) {
  console.log(`[PROBE] ${label} :: ${JSON.stringify(payload)}`);
}
```

Run them with:

```bash
npx ng test --watch=false --reporters=verbose
```

## The shorthand, and what it throws away

The one-liner everybody shows is genuinely lovely:

```typescript
const items = signal<Item[]>([item(1), item(2), item(3)]);
const selected = linkedSignal(() => items()[0] ?? null);

const initial = selected()?.id;
selected.set(item(3));
const afterUserPick = selected()?.id;

// A background refresh prepends a new item.
items.set([item(0), item(1), item(2), item(3)]);
const afterRefresh = selected()?.id;

probe('shorthand-resets', { initial, afterUserPick, afterRefresh });
```

```text
[PROBE] shorthand-resets :: {"initial":1,"afterUserPick":3,"afterRefresh":0}
```

Writable, and it resets when the source moves. Exactly as advertised. The user picked #3 and ended up on #0.

That much is well known. Here is the part that is not.

## A refresh that changes nothing still resets you

Same setup, except the "refresh" returns the identical three items:

```typescript
const items = signal<Item[]>([item(1), item(2), item(3)]);
const selected = linkedSignal(() => items()[0] ?? null);

selected.set(item(3));
const before = selected()?.id;

// Same contents, brand new array reference - a very common HTTP refresh result.
items.set([item(1), item(2), item(3)]);
const afterIdenticalContents = selected()?.id;

probe('new-array-same-contents', { before, afterIdenticalContents });
```

```text
[PROBE] new-array-same-contents :: {"before":3,"afterIdenticalContents":1}
```

The selection is gone, and nothing about the data changed.

This is not a `linkedSignal` bug. Signals compare with `Object.is` by default, and `[a, b, c]` is never `Object.is` to another `[a, b, c]`. Every `rxResource` reload, every polling interval, every "pull to refresh" hands you a fresh array. **A list that refreshes on a timer will unselect your user on every tick.**

## Fix 1: teach the source what "changed" means

The cheapest fix is not in the `linkedSignal` at all. It is on the signal feeding it:

```typescript
const sameIds = (a: Item[], b: Item[]) =>
  a.length === b.length && a.every((x, i) => x.id === b[i].id);

const items = signal<Item[]>([item(1), item(2), item(3)], { equal: sameIds });
const selected = linkedSignal(() => items()[0] ?? null);

selected.set(item(3));
const before = selected()?.id;

items.set([item(1), item(2), item(3)]);      // identical contents
const afterIdentical = selected()?.id;

items.set([item(1), item(2)]);               // genuinely different
const afterRealChange = selected()?.id;

probe('equal-on-the-source', { before, afterIdentical, afterRealChange });
```

```text
[PROBE] equal-on-the-source :: {"before":3,"afterIdentical":3,"afterRealChange":1}
```

An identical refresh is now a non-event, and a real change still resets. One `equal` option, problem gone. If you take one thing from this post, take this line.

## What is actually inside `previous`

The long form of `linkedSignal` takes `source` and `computation`, and hands the computation a `previous` object. The docs describe it; I wanted to see it:

```typescript
const items = signal<Item[]>([item(1), item(2)]);
const seen: unknown[] = [];

const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (source, previous) => {
    seen.push({
      sourceIds: source.map((i) => i.id),
      previousIsUndefined: previous === undefined,
      previousValueId: previous?.value?.id ?? null,
      previousSourceIds: previous?.source?.map((i) => i.id) ?? null,
    });
    return source[0] ?? null;
  },
});

selected();                       // first computation
selected.set(item(2));            // a manual write
items.set([item(7), item(8)]);    // source change -> recomputation
selected();

probe('previous-shape', seen);
```

```text
[PROBE] previous-shape :: [
  {"sourceIds":[1,2],"previousIsUndefined":true,"previousValueId":null,"previousSourceIds":null},
  {"sourceIds":[7,8],"previousIsUndefined":false,"previousValueId":2,"previousSourceIds":[1,2]}
]
```

Two useful facts. `previous` is `undefined` on the very first run, so `previous?.value` is not optional politeness, it is required. And `previous.value` is **2**, the value the user wrote by hand, not the value the computation last returned. The manual `.set()` is what you get back.

## Fix 2: keep the selection if it is still valid

With `previous.value` available, the sensible rule writes itself:

```typescript
const variants = signal<Item[]>([item(1), item(2), item(3)]);

const selected = linkedSignal<Item[], Item | null>({
  source: variants,
  computation: (next, previous) => {
    if (!previous?.value) return next[0] ?? null;
    return next.find((v) => v.id === previous.value!.id) ?? next[0] ?? null;
  },
});

selected.set(item(3));
const picked = selected()?.id;

variants.set([item(0), item(1), item(2), item(3)]);   // refresh, #3 survives
const afterRefresh = selected()?.id;

variants.set([item(1), item(2)]);                      // #3 deleted
const afterDeletion = selected()?.id;

probe('keep-selection', { picked, afterRefresh, afterDeletion });
```

```text
[PROBE] keep-selection :: {"picked":3,"afterRefresh":3,"afterDeletion":1}
```

Selection survives a refresh, and falls back gracefully when the item genuinely disappears. This is the pattern worth memorising.

## The trap: `computation` tracks everything it reads

Here is the one that caught me out. I assumed `computation` only reacts to `source`, because `source` has its own dedicated slot in the API. It does not.

```typescript
const items = signal<Item[]>([item(1), item(2), item(3)]);
const preferredId = signal(2);
let computationRuns = 0;

const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (source) => {
    computationRuns++;
    // Reading a signal that is NOT the source:
    const wanted = preferredId();
    return source.find((i) => i.id === wanted) ?? source[0] ?? null;
  },
});

const first = selected()?.id;
const runsAfterFirst = computationRuns;

// Change ONLY the non-source signal.
preferredId.set(3);
const afterPreferredChange = selected()?.id;
const runsAfterPreferredChange = computationRuns;

// Now touch the real source.
items.set([item(1), item(2), item(3), item(4)]);
const afterSourceChange = selected()?.id;
const runsAfterSourceChange = computationRuns;

probe('computation-tracking', {
  first, runsAfterFirst,
  afterPreferredChange, runsAfterPreferredChange,
  afterSourceChange, runsAfterSourceChange,
});
```

```text
[PROBE] computation-tracking :: {"first":2,"runsAfterFirst":1,"afterPreferredChange":3,
"runsAfterPreferredChange":2,"afterSourceChange":3,"runsAfterSourceChange":3}
```

Run count went from 1 to 2 when I touched `preferredId`, and `items` never moved.

**Every signal you read inside `computation` becomes a reset trigger.** Read a "sort ascending" toggle in there and flipping the sort re-runs your selection logic. That is fine if your computation honours `previous.value`, and it quietly discards user state if it does not:

```typescript
const sortAscending = signal(true);   // a totally unrelated UI toggle

const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (list, previous) => {
    const ordered = sortAscending() ? list : [...list].reverse();
    if (previous?.value && ordered.some((i) => i.id === previous.value!.id)) {
      return previous.value;
    }
    return ordered[0] ?? null;
  },
});

selected.set(item(3));
const userPicked = selected()?.id;

sortAscending.set(false);             // items never changed
const afterUnrelatedToggle = selected()?.id;

probe('non-source-signal-recompute', { userPicked, afterUnrelatedToggle });
```

```text
[PROBE] non-source-signal-recompute :: {"userPicked":3,"afterUnrelatedToggle":3}
```

Written defensively, the selection survives. Written as `return ordered[0]`, it would not have. The recomputation happens either way.

## Why not just use an effect?

This is the comparison the feature exists for, so I ran both side by side and read the values at two different moments: right after the source changed, and again after effects flushed.

```typescript
const items = signal<Item[]>([item(1), item(2)]);

// The old way.
const effectSelected = signal<Item | null>(items()[0]);
let effectRuns = 0;
effect(() => {
  const list = items();
  untracked(() => { effectRuns++; effectSelected.set(list[0] ?? null); });
}, { injector });

// The new way.
const linkedSelected = linkedSignal(() => items()[0] ?? null);

TestBed.tick();                       // let the initial effect run
const effectRunsAfterInit = effectRuns;

items.set([item(9), item(1), item(2)]);

const readBeforeFlush = {
  effect: effectSelected()?.id,
  linked: linkedSelected()?.id,
};

TestBed.tick();                       // flush effects

const readAfterFlush = {
  effect: effectSelected()?.id,
  linked: linkedSelected()?.id,
};

probe('timing', { effectRunsAfterInit, readBeforeFlush, readAfterFlush, effectRuns });
```

```text
[PROBE] timing :: {"effectRunsAfterInit":1,"readBeforeFlush":{"effect":1,"linked":9},
"readAfterFlush":{"effect":9,"linked":9},"effectRuns":2}
```

Look at `readBeforeFlush`. The effect-based signal still says **1**. The `linkedSignal` already says **9**.

That gap is the whole argument. With an effect, there is a window where your derived state is stale, because effects run *after* the change, on Angular's schedule. Anything that reads during that window - a computed, a guard, a service call, another effect - reads the old value. `linkedSignal` has no window, because it recomputes on read.

The value is never wrong for long. It is just wrong at the exact moment something else looks at it, which is the hardest kind of bug to reproduce on purpose.

## It is lazy, and it memoizes

Worth knowing before you put expensive work in a computation:

```typescript
const items = signal<Item[]>([item(1)]);
let runs = 0;
const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (list) => { runs++; return list[0] ?? null; },
});

selected();
const afterFirstRead = runs;

items.set([item(2)]);
const afterSetBeforeRead = runs;      // is it eager or lazy?

selected(); selected(); selected();
const afterThreeReads = runs;

probe('laziness', { afterFirstRead, afterSetBeforeRead, afterThreeReads });
```

```text
[PROBE] laziness :: {"afterFirstRead":1,"afterSetBeforeRead":1,"afterThreeReads":2}
```

Changing the source does not run the computation. Reading afterwards does, once, and three reads share one result. Same laziness as `computed`.

And the obvious difference from `computed`, confirmed rather than assumed:

```typescript
const derived = computed(() => items()[0]);
const linked = linkedSignal(() => items()[0]);

probe('writability', {
  computedHasSet: 'set' in derived,
  linkedHasSet: 'set' in linked,
  linkedHasUpdate: 'update' in linked,
  linkedHasAsReadonly: 'asReadonly' in linked,
});
```

```text
[PROBE] writability :: {"computedHasSet":false,"linkedHasSet":true,"linkedHasUpdate":true,"linkedHasAsReadonly":true}
```

## Which one do you reach for?

| Scenario | Use |
| --- | --- |
| Pure derived data, never written by hand | `computed()` |
| Read-only async data from a server | `resource()` / `rxResource()` |
| Writable state that resets when a source changes | `linkedSignal()` |
| Talking to something outside the signal graph: analytics, canvas, localStorage | `effect()` |

If you are writing `untracked()` inside an `effect()` in order to `.set()` another signal, that is a `linkedSignal` wearing a disguise.

## Summary

* **`linkedSignal` resets on reference change, not on value change.** A refresh returning byte-identical data still wiped my selection, `3` back to `1`.
* **Put `equal` on the source signal.** It is a one-line fix and it made the identical refresh a non-event.
* **`previous` is `undefined` on the first run**, and `previous.value` gives you the user's manual `.set()`, which is exactly what you want to preserve.
* **`computation` tracks every signal it reads**, not just `source`. Reading an unrelated toggle in there turns that toggle into a reset trigger.
* **The effect version is stale until effects flush.** I measured `1` where `linkedSignal` already said `9`. That window is where the bugs live.
* **It is lazy and memoized**, so three reads cost one computation.

Friendly closing tip: after you convert an `effect()` to a `linkedSignal`, click something in the UI and then trigger a refresh that returns the same data. If your selection survives that, you got it right.
