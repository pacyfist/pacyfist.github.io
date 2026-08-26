---
# SEO Target Queries:
#   Google: "angular linkedsignal vs computed", "angular linkedsignal", "angular linkedsignal previous"
#   Bing:   "angular linked signal", "linkedsignal vs effect", "how to use linkedsignal angular"
tags: ["typescript", "angular", "signals", "linkedsignal", "reactivity"]
categories: ["typescript", "angular"]
title: "Angular linkedSignal vs computed: The Reset You Missed"
image:
  path: /assets/img/2026-08-20/main.jpg
  alt: A list that helpfully unselects your choice every time it refreshes.
published: false
---

Before the refresh my selection said `3`. After a refresh that returned the exact same three items, it said `1`.

Nothing about the data had changed. The array was new, the contents were identical, and my selection was gone anyway.

So I stopped guessing and wrote a test that prints the selection before and after every kind of refresh I could think of.

## What I am measuring with

There are already good explanations of what `linkedSignal` *is*, so this post starts where they stop.

A default Angular 22 workspace, which now ships Vitest as the test runner, [with the migration caveats I hit here](https://www.pacyfist.dev/posts/angular-karma-to-vitest-migration/):

```bash
npx @angular/cli@22 new signalslab --style=scss --ssr=false --defaults
```

That scaffolds the workspace and installs the dependencies. The only output worth reading is what it installed:

```bash
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

Every spec in this post starts from these two imports and this tiny fixture:

```typescript
import { signal, computed, linkedSignal, effect, untracked, Injector } from '@angular/core';
import { TestBed } from '@angular/core/testing';

interface Item { id: number; name: string; }

const item = (id: number): Item => ({ id, name: `Item #${id}` });
```

Every result below is printed by this helper, so no number in this post is one I typed by hand:

```typescript
function probe(label: string, payload: unknown) {
  console.log(`[PROBE] ${label} :: ${JSON.stringify(payload)}`);
}
```

Run them with:

```bash
npx ng test --watch=false --reporters=verbose
```

Without `--reporters=verbose` the runner swallows `console.log`, so every `text` block below is a line from that run.

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

This is not a `linkedSignal` bug, and the reason for it is the load-bearing idea in the whole post. Everything else here is a consequence of it, so I did not want to take it on trust. The probe below sets the **same array back** and then sets a **new array with identical contents**, so the two cases sit next to each other:

```typescript
const arr = [item(1), item(2), item(3)];
const items = signal<Item[]>(arr);
const selected = linkedSignal(() => items()[0] ?? null);

selected.set(item(3));
const before = selected()?.id;

items.set(arr);                         // the very same reference
const afterSameReference = selected()?.id;

items.set([item(1), item(2), item(3)]); // new reference, same contents
const afterNewReference = selected()?.id;

probe('object-is-identity', {
  objectIsSameArray: Object.is(arr, arr),
  objectIsEqualArrays: Object.is([1, 2], [1, 2]),
  before,
  afterSameReference,
  afterNewReference,
});
```

```text
[PROBE] object-is-identity :: {"objectIsSameArray":true,"objectIsEqualArrays":false,"before":3,"afterSameReference":3,"afterNewReference":1}
```

Same reference, the selection stays at **3**. New reference with identical contents, it drops to **1**. And `Object.is([1, 2], [1, 2])` is `false`.

Signals compare with `Object.is`, which asks "is this the same object", not "does it hold the same stuff". Two arrays holding `1, 2, 3` are still two arrays.

Every `rxResource` reload, every polling interval, every pull-to-refresh hands you a fresh one, and [the rxResource post](https://www.pacyfist.dev/posts/angular-rxresource-error-handling/) has the probe output for that. **A list that refreshes on a timer will unselect your user on every tick.**

## The trap: `computation` tracks everything it reads

This is the one I had backwards. I assumed `computation` only reacts to `source`, because `source` has its own dedicated slot in the API. It does not.

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
[PROBE] computation-tracking :: {"first":2,"runsAfterFirst":1,"afterPreferredChange":3,"runsAfterPreferredChange":2,"afterSourceChange":3,"runsAfterSourceChange":3}
```

Run count went from 1 to 2 when I touched `preferredId`, and `items` never moved.

**Every signal you read inside `computation` becomes a reset trigger.** Read a "sort ascending" toggle in there and flipping the sort re-runs your selection logic.

So that is two ways to lose a selection: a refresh that changed nothing, and a toggle that has nothing to do with the data. Here are the two fixes.

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

An identical refresh is now a non-event, and a real change still resets. One `equal` option, problem gone.

Now the part that trips people up. `linkedSignal` takes an `equal` option of its own, so the obvious move is to put it there instead. That does not fix this, and it is worth being exact about why, because both placements are real fixes for two different problems.

**`equal` on the source signal stops the linkedSignal from resetting.** The source decides nothing changed, so the computation never re-runs, and the user's selection stays put. That is the fix in this section.

**`equal` on the linkedSignal itself does not stop the reset. It stops the notification.** The computation still re-runs and the value still falls back to `1`, but downstream consumers are never told the value changed. That is no help here, and it is exactly the right tool when the problem is a loop rather than a lost selection: it is what stops an auto-save effect firing on the value it just wrote. I measure that case in [the SignalStore post](https://www.pacyfist.dev/posts/signal-forms-ngrx-signalstore/).

Two placements, two jobs. Here is the probe that keeps them apart, with an identical refresh hitting both at once:

```typescript
const sameIds = (a: Item[], b: Item[]) =>
  a.length === b.length && a.every((x, i) => x.id === b[i].id);

const itemsPlain = signal<Item[]>([item(1), item(2), item(3)]);
const onLinked = linkedSignal(() => itemsPlain()[0] ?? null, {
  equal: (a, b) => a?.id === b?.id,
});

const itemsEqual = signal<Item[]>([item(1), item(2), item(3)], { equal: sameIds });
const onSource = linkedSignal(() => itemsEqual()[0] ?? null);

onLinked.set(item(3));
onSource.set(item(3));
const before = { onLinked: onLinked()?.id, onSource: onSource()?.id };

itemsPlain.set([item(1), item(2), item(3)]);
itemsEqual.set([item(1), item(2), item(3)]);
const afterIdenticalRefresh = { onLinked: onLinked()?.id, onSource: onSource()?.id };

probe('equal-placement', { before, afterIdenticalRefresh });
```

```text
[PROBE] equal-placement :: {"before":{"onLinked":3,"onSource":3},"afterIdenticalRefresh":{"onLinked":1,"onSource":3}}
```

Both start on **3**. After the identical refresh, `equal` on the linkedSignal is back to **1** and `equal` on the source is still **3**. If you take one thing from this post, take that distinction.

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
[PROBE] previous-shape :: [{"sourceIds":[1,2],"previousIsUndefined":true,"previousValueId":null,"previousSourceIds":null},{"sourceIds":[7,8],"previousIsUndefined":false,"previousValueId":2,"previousSourceIds":[1,2]}]
```

That transcript settles three questions I had.

First, `previous` is `undefined` on the very first run. So `previous?.value` is not optional politeness, it is required.

Second, `previous.source` is the array the computation saw *last* time, `[1,2]`, while `source` is the new `[7,8]`. That is how you diff a refresh against what it replaced.

Third, `previous.value` is **2**, the value the user wrote by hand, and not the `1` the computation last returned.

That third one is easy to over-read as "a manual `.set()` is what you get back". It is worth checking, because if manual writes really were stored separately you could use `previous.value` to tell user input apart from computed state. So I ran the same shape with nobody calling `.set()` anywhere, and made the computation return the **last** item so its own output is easy to spot:

```typescript
const items = signal<Item[]>([item(1), item(2)]);
const seen: unknown[] = [];
let sourceSnapshot: Item[] | null = null;

const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (source, previous) => {
    seen.push({
      sourceIds: source.map((i) => i.id),
      previousValueId: previous?.value?.id ?? null,
      previousSourceIsPreviousArray:
        previous === undefined ? null : Object.is(previous.source, sourceSnapshot),
      previousSourceIsCurrentArray:
        previous === undefined ? null : Object.is(previous.source, source),
    });
    sourceSnapshot = source;
    // Deliberately return the LAST item, not source[0], so a computed
    // result is distinguishable from a manual set.
    return source[source.length - 1] ?? null;
  },
});

selected();                       // first computation -> id 2
items.set([item(7), item(8)]);    // source change, no manual set anywhere
selected();

probe('previous-value-no-manual-set', seen);
```

```text
[PROBE] previous-value-no-manual-set :: [{"sourceIds":[1,2],"previousValueId":null,"previousSourceIsPreviousArray":null,"previousSourceIsCurrentArray":null},{"sourceIds":[7,8],"previousValueId":2,"previousSourceIsPreviousArray":true,"previousSourceIsCurrentArray":false}]
```

`previousValueId` is **2** again, and this time it is the computation's own last return. Nobody called `set()`.

So **`previous.value` is just whatever the signal is holding right now**: the computation's last return, or the user's `.set()` if that came later. In the first probe the user's `.set()` came later, which is why you got **2** back there. The same probe confirms `previous.source` too: it is the previous array (`true`) and not the current one (`false`).

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

## Does Fix 2 also cover the trap?

Fix 2 was written for a source change. The trap was an unrelated toggle. Same guard, or does the toggle need its own handling? Fresh list, fresh linked signal, and one sort toggle that has nothing to do with the data:

```typescript
const items = signal<Item[]>([item(1), item(2), item(3)]);
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

Same guard, and the pick survives a recomputation the source knew nothing about.

It is tempting to stop there and say that written as a plain `return ordered[0]`, the selection would have gone back to `1`. Tempting, and wrong for this data. Here is the same test with the guard deleted:

```typescript
// the same block again, with one edit: the guard is gone
const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (list) => {
    const ordered = sortAscending() ? list : [...list].reverse();
    return ordered[0] ?? null;   // no previous.value guard
  },
});

// same pick, same toggle, same two reads as above
probe('unguarded-non-source-recompute', { userPicked, afterUnrelatedToggle });
```

```text
[PROBE] unguarded-non-source-recompute :: {"userPicked":3,"afterUnrelatedToggle":3}
```

**3** either way. Reversing `[1, 2, 3]` puts item #3 at the front, so `ordered[0]` lands back on the user's pick by pure luck. With this data the guard is doing nothing you can see.

Which is exactly why the comparison has to be run rather than assumed. Both shapes, side by side, on a pick that reversal does not promote to the front:

```typescript
const items = signal<Item[]>([item(1), item(2), item(3)]);
const sortAscending = signal(true);

const guarded = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (list, previous) => {
    const ordered = sortAscending() ? list : [...list].reverse();
    if (previous?.value && ordered.some((i) => i.id === previous.value!.id)) {
      return previous.value;
    }
    return ordered[0] ?? null;
  },
});

const unguarded = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (list) => {
    const ordered = sortAscending() ? list : [...list].reverse();
    return ordered[0] ?? null;
  },
});

guarded.set(item(2));
unguarded.set(item(2));
const picked = { guarded: guarded()?.id, unguarded: unguarded()?.id };

sortAscending.set(false);          // items never changed
const afterToggle = { guarded: guarded()?.id, unguarded: unguarded()?.id };

probe('guarded-vs-unguarded', { picked, afterToggle });
```

```text
[PROBE] guarded-vs-unguarded :: {"picked":{"guarded":2,"unguarded":2},"afterToggle":{"guarded":2,"unguarded":3}}
```

Both start on **2**. After the toggle the guarded one is still **2** and the unguarded one has jumped to **3**. **The guard is what saves the selection, and the recomputation happens either way.**

## It is lazy, and it memoizes

Every guard above sits inside a computation, so it is worth knowing when that computation actually runs before you put anything expensive in one. And since the whole point of `linkedSignal` is to replace a `computed` you needed to write to, the honest question is whether it costs you the laziness `computed` has. So I counted both:

```typescript
const items = signal<Item[]>([item(1)]);
let runs = 0;
let computedRuns = 0;

const selected = linkedSignal<Item[], Item | null>({
  source: items,
  computation: (list) => { runs++; return list[0] ?? null; },
});
const derived = computed<Item | null>(() => { computedRuns++; return items()[0] ?? null; });

selected(); derived();
const afterFirstRead = { linked: runs, computed: computedRuns };

items.set([item(2)]);
const afterSetBeforeRead = { linked: runs, computed: computedRuns };   // eager or lazy?

selected(); selected(); selected();
derived(); derived(); derived();
const afterThreeReads = { linked: runs, computed: computedRuns };

probe('laziness', { afterFirstRead, afterSetBeforeRead, afterThreeReads });
```

```text
[PROBE] laziness :: {"afterFirstRead":{"linked":1,"computed":1},"afterSetBeforeRead":{"linked":1,"computed":1},"afterThreeReads":{"linked":2,"computed":2}}
```

Changing the source runs neither one. Reading afterwards runs each once, and three reads share one result. **The two counters are identical at every step**, so switching to `linkedSignal` costs you nothing in laziness.

Everything above depends on being able to write the signal by hand, because that manual `.set()` is the user's selection. So here is the one difference from `computed` that everybody states without checking:

```typescript
const items = signal<Item[]>([item(1)]);
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

`computed` really has no `set`, so there is no way to let a user override a `computed` value. You end up keeping a second signal and an `if` that picks between them, which is the exact code `linkedSignal` deletes.

## Why not just use an effect?

This is the comparison the feature exists for. So I ran both side by side and read each one twice: once right after the source changed, once after effects flushed.

```typescript
const injector = TestBed.inject(Injector);

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

`TestBed.tick()` is what runs the pending effects in a zoneless test, which is the only reason the two reads can happen at different moments.

```text
[PROBE] timing :: {"effectRunsAfterInit":1,"readBeforeFlush":{"effect":1,"linked":9},"readAfterFlush":{"effect":9,"linked":9},"effectRuns":2}
```

Look at `readBeforeFlush`. The effect-based signal still says **1**. The `linkedSignal` already says **9**.

That gap is the whole argument. An effect updates your derived state *after* the fact, on Angular's schedule, so there is a window where the old value is still sitting there, like a scoreboard that only refreshes between innings.

Anything reading in that window gets the stale number. `linkedSignal` has no window at all, because it does the work when you read it.

The value is never wrong for long. It is just wrong at the exact moment something else looks at it, which is the hardest kind of bug to reproduce on purpose.

## Which one do you reach for?

| Scenario | Use |
| --- | --- |
| Pure derived data, never written by hand | `computed()` |
| Read-only async data from a server | `resource()` / [`rxResource()`](https://www.pacyfist.dev/posts/angular-rxresource-error-handling/) |
| Writable state that resets when a source changes | `linkedSignal()` |
| Talking to something outside the signal graph: analytics, canvas, localStorage | `effect()` |

If you are writing `untracked()` inside an `effect()` in order to `.set()` another signal, that is a `linkedSignal` wearing a disguise.

## Summary

* **`linkedSignal` resets on reference change, not on value change.** A refresh returning byte-identical data still wiped my selection, `3` back to `1`, because `Object.is` compares objects and not contents.
* **Put `equal` on the source signal to stop the reset.** `equal` on the linkedSignal itself does not stop it. That placement only stops downstream consumers being notified, which is a different fix for a different problem.
* **`previous` is `undefined` on the first run**, and `previous.value` is simply the signal's current value, which is how you preserve a manual `.set()` across a source change.
* **`computation` tracks every signal it reads**, not just `source`. Reading an unrelated toggle in there turns that toggle into a reset trigger.
* **Check the counterfactual instead of asserting it.** With this list, the unguarded computation returned the right item anyway; only picking an item that reversal does not promote showed the guard actually working.
* **The effect version is stale until effects flush.** I measured `1` where `linkedSignal` already said `9`. That window is where the bugs live.
* **It is lazy and memoized, and `computed` counts identically**, so three reads cost one computation.

The five-second check, after you convert an `effect()` to a `linkedSignal`: click something in the UI and then trigger a refresh that returns the same data. If your selection survives that, you got it right.
