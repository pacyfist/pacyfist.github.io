---
# SEO Target Queries:
#   Google: "angular signal forms ngrx signalstore", "angular signal store and forms", "signal forms writable signal"
#   Bing:   "angular signal store form", "ngrx signalstore signal forms", "angular signal store best practices"
tags: ["typescript", "angular", "signal forms", "ngrx", "signalstore"]
categories: ["typescript", "angular"]
title: "Signal Forms + NgRx SignalStore: The Missing Bridge"
image:
  path: /assets/img/2026-08-21/main.jpg
  alt: Two pieces that refuse to click together until something sits between them.
published: false
---

The [Signal Forms post](https://www.pacyfist.dev/posts/angular-signal-forms-14-awkward-questions-and-one-nasty-surprise/) ended with a signup form built out of a plain `signal()` and a schema, and it worked beautifully. The obvious next question is what happens when that data lives in an NgRx SignalStore instead of a component field.

The answer is short. `form(store.user)` does not compile, and it is not close.

The piece that makes it compile is a `linkedSignal`, which is exactly what [yesterday's post](https://www.pacyfist.dev/posts/angular-linkedsignal-vs-computed/) is about. If `source`, `computation` and `equal` are new words, read that one first. Everything below leans on them.

Everything below runs against one store and one form, both real, in an Angular 22 workspace with `@ngrx/signals` 22 installed. Two of the answers are things I would have shipped.

## One store, one form, one spec file

```bash
npm install @ngrx/signals@22 @ngrx/operators
```

That pulls in `@ngrx/signals` 22.0.0. Two checks pin the workspace down: `ng version` for Angular itself, and a one-liner for the `@ngrx/signals` version, which `ng version` does not list.

```bash
npx ng version
```

The real banner is thirty lines of ASCII logo and package table. Below is an excerpt of it. A `...` line is where rows were dropped, and nothing in between was retyped:

```text
...
Angular CLI       : 22.1.6
Angular           : 22.1.3
Node.js           : 26.5.0
Package Manager   : npm 11.17.0
Operating System  : linux x64

┌───────────────────────────┬───────────────────┬───────────────────┐
│ Package                   │ Installed Version │ Requested Version │
├───────────────────────────┼───────────────────┼───────────────────┤
...
│ @angular/core             │ 22.1.3            │ ^22.1.0           │
│ @angular/forms            │ 22.1.3            │ ^22.1.0           │
...
│ typescript                │ 6.0.3             │ ~6.0.2            │
│ vitest                    │ 4.1.11            │ ^4.0.8            │
└───────────────────────────┴───────────────────┴───────────────────┘
```

```bash
node -e "console.log(require('@ngrx/signals/package.json').version)"
```

```text
22.0.0
```

Here is the store every experiment below runs against:

```typescript
export interface UserProfile {
  name: string;
  email: string;
  bio: string;
}

export const UserStore = signalStore(
  { providedIn: 'root' },
  withState({
    user: { name: 'Filip', email: 'filip@example.com', bio: '' } as UserProfile,
    isSaving: false,
    saveCount: 0,
  }),
  withComputed((store) => ({
    displayName: computed(() => store.user().name || '(nobody)'),
  })),
  withMethods((store) => ({
    saveProfile(next: UserProfile) {
      patchState(store, { user: next, isSaving: false, saveCount: store.saveCount() + 1 });
    },
    // The auto-save path: a method, because only methods may write state.
    autoSave(next: UserProfile) {
      patchState(store, { user: next, saveCount: store.saveCount() + 1 });
    },
    // Simulates a push arriving from the server / another tab.
    serverPush(next: UserProfile) {
      patchState(store, { user: next });
    },
  })),
);
```

## The harness these snippets run in

Before the traps, the boring part, because everything below leans on it.

The same one-line `probe()` helper prints every result, so no number in this post is one I typed by hand.

```typescript
function probe(label: string, payload: unknown) {
  console.log(`[PROBE] ${label} :: ${JSON.stringify(payload)}`);
}
```

Most of the experiments are the body of an `it()` in a Vitest spec, and they all open the same way:

```typescript
const store = TestBed.inject(UserStore);

TestBed.runInInjectionContext(() => {
  const model = linkedSignal<UserProfile, UserProfile>({
    source: store.user,
    computation: (fromStore) => ({ ...fromStore }),   // the bridge
  });

  const f = form(model, (path) => {
    required(path.name, { message: 'Name is required' });
    email(path.email, { message: 'Not an email' });
  });

  // the snippet goes here, and uses store, model and f
});
```

**That wrapper is not decoration.** `linkedSignal()` and `form()` both need an injection context, and a bare call outside one throws before your probe ever gets to run. A component hands you that context for free. A spec has to ask for it.

The `linkedSignal` in the middle is the bridge this whole post is about, and the next two sections are about why it has to be there at all. From here on, a snippet marked **same harness** is the body of that wrapper with only its own lines shown, and `store`, `model` and `f` are the ones declared above. The three snippets that change the bridge write their `linkedSignal` out in full, because the change is the whole point of them.

## Why they refuse to connect

`form()` has three overloads in Angular 22, and all three agree on the first parameter:

```bash
grep -n "declare function form<" node_modules/@angular/forms/types/_structure-chunk.d.ts
```

```text
1861:declare function form<TModel>(model: WritableSignal<TModel>): FieldTree<TModel>;
1909:declare function form<TModel>(model: WritableSignal<TModel>, schemaOrOptions: SchemaOrSchemaFn<TModel> | FormOptions<TModel>): FieldTree<TModel>;
1955:declare function form<TModel>(model: WritableSignal<TModel>, schema: SchemaOrSchemaFn<TModel>, options: FormOptions<TModel>): FieldTree<TModel>;
```

The extra arguments are the schema and the options, and the forms further down this post use the second one. The first parameter is a `WritableSignal<TModel>` in all three, and the doc comment above them explains why:

> `form` uses the given model as the source of truth and *does not* maintain its own copy of the data. This means that updating the value on a `FieldState` updates the originally passed in model as well.

A Signal Form does not hold your data. It writes straight back into the signal you handed it.

So it needs a `WritableSignal`, and a SignalStore hands you the opposite. Here is the whole question in one file:

```typescript
// This file is NEVER imported by the app. It exists to be type-checked.
import { form } from '@angular/forms/signals';
import { inject } from '@angular/core';
import { UserStore } from './user.store';

export function bindStoreDirectlyToForm() {
  const store = inject(UserStore);
  return form(store.user);
}
```

At this point that file is the only thing in the lab that is meant to fail, so the compiler prints one error:

```bash
npx tsc --noEmit -p tsconfig.app.json
```

```text
src/app/lab/store-form-compile.ts(9,15): error TS2345: Argument of type 'DeepSignal<UserProfile>' is not assignable to parameter of type 'WritableSignal<unknown>'.
  Type 'DeepSignal<UserProfile>' is missing the following properties from type 'WritableSignal<unknown>': set, update, asReadonly, [ɵWRITABLE_SIGNAL]
```

`DeepSignal` is the nice part of SignalStore. Every property of your state is its own signal, so `store.user.name` is a signal too. A template reading `store.user.name()` does not re-render when `bio` changes.

That is the claim. Before building a bridge on top of it, it is worth printing what `store.user` really is:

```typescript
const store = TestBed.inject(UserStore);
probe('store-signal-shape', {
  userIsFunction: typeof store.user === 'function',
  userHasSet: 'set' in store.user,
  // DeepSignal: every property is its own signal
  nameIsFunction: typeof store.user.name === 'function',
  nameHasSet: 'set' in store.user.name,
  nameValue: store.user.name(),
});
```

```text
[PROBE] store-signal-shape :: {"userIsFunction":true,"userHasSet":true,"nameIsFunction":true,"nameHasSet":false,"nameValue":"Filip"}
```

The fine-grained half of the claim is the one worth checking, because it is the reason to keep this shape at all. If a bio change re-ran everything that reads the name, `DeepSignal` would be decoration. So here is a `computed` that reads only the name, counting its own runs across a bio push and then a name push:

```typescript
const store = TestBed.inject(UserStore);
TestBed.runInInjectionContext(() => {
  let nameComputedRuns = 0;
  const watchName = computed(() => { nameComputedRuns++; return store.user.name(); });
  watchName();
  const runsAfterFirstRead = nameComputedRuns;
  store.serverPush({ name: 'Filip', email: 'filip@example.com', bio: 'CHANGED BIO' });
  watchName();
  const runsAfterBioChange = nameComputedRuns;
  store.serverPush({ name: 'NEW NAME', email: 'filip@example.com', bio: 'CHANGED BIO' });
  watchName();
  probe('deep-signal-fine-grained', {
    runsAfterFirstRead,
    runsAfterBioChange,
    runsAfterNameChange: nameComputedRuns,
  });
});
```

```text
[PROBE] deep-signal-fine-grained :: {"runsAfterFirstRead":1,"runsAfterBioChange":1,"runsAfterNameChange":2}
```

The bio change did not re-run it. The name change did. **`DeepSignal` is fine-grained for real.**

Now look back at `userHasSet: true` in the first probe. That is not a typo, and it leads somewhere uncomfortable.

## The read-only store is only read-only at compile time

TypeScript says `store.user` has no `set`. JavaScript disagrees:

```typescript
const store = TestBed.inject(UserStore);
const anyUser = store.user as any;
let calling: string;
try {
  anyUser.set({ name: 'Hacked', email: 'x@y.z', bio: '' });
  calling = `no throw, name is now ${store.user.name()}`;
} catch (e) {
  calling = `${(e as Error).constructor.name}: ${(e as Error).message}`;
}
probe('deep-signal-set', {
  inOperatorSaysSet: 'set' in store.user,
  typeofSet: typeof anyUser.set,
  result: calling,
});
```

```text
[PROBE] deep-signal-set :: {"inOperatorSaysSet":true,"typeofSet":"function","result":"no throw, name is now Hacked"}
```

One `as any` and the store's state is writable from anywhere, with no error and no warning. **SignalStore's immutability is a type-level contract, not a runtime guard.** Do not reach for that cast because a form will not bind, and do not let a code review wave one through.

The cast is not even required. The object the store hands you is the object it keeps, and dev mode does not freeze it:

```typescript
const store = TestBed.inject(UserStore);
const snapshot = store.user();
let mutateResult: string;
try {
  (snapshot as any).name = 'MutatedInPlace';
  mutateResult = `no throw, store.user.name() is now ${store.user.name()}`;
} catch (e) {
  mutateResult = `${(e as Error).constructor.name}: ${(e as Error).message}`;
}
probe('runtime-freeze', {
  ngDevMode: typeof (globalThis as any).ngDevMode !== 'undefined' && !!(globalThis as any).ngDevMode,
  isFrozen: Object.isFrozen(snapshot),
  mutateResult,
});
```

```text
[PROBE] runtime-freeze :: {"ngDevMode":true,"isFrozen":false,"mutateResult":"no throw, store.user.name() is now MutatedInPlace"}
```

`isFrozen:false` in dev mode, and assigning to a property of the snapshot changed what `store.user.name()` returns. Remember that one, because it decides how the bridge is built two sections down.

The compiler does defend the front door properly, though. Here is the whole file that tries to patch the store from outside it:

```typescript
// AUDIT PROBE: does patchState from outside the store compile?
// This file is NEVER imported by the app. It exists to be type-checked.
import { inject } from '@angular/core';
import { patchState } from '@ngrx/signals';
import { UserStore } from './user.store';

export function patchStoreFromComponent() {
  const store = inject(UserStore);
  const current = store.user();
  patchState(store, { user: current });
}
```

Both throwaway files are in the project now, so the same command prints two errors. The new one comes first:

```bash
npx tsc --noEmit -p tsconfig.app.json
```

```text
src/app/lab/patch-state-compile.ts(10,14): error TS2345: Argument of type '{ user: DeepSignal<UserProfile>; isSaving: Signal<boolean>; saveCount: Signal<number>; displayName: Signal<string>; saveProfile: (next: UserProfile) => void; autoSave: (next: UserProfile) => void; serverPush: (next: UserProfile) => void; } & StateSource<...>' is not assignable to parameter of type 'WritableStateSource<{ user: UserProfile; isSaving: boolean; saveCount: number; }>'.
  The types of '[STATE_SOURCE].user' are incompatible between these types.
    Type 'Signal<UserProfile>' is missing the following properties from type 'WritableSignal<UserProfile>': set, update, asReadonly, [ɵWRITABLE_SIGNAL]
src/app/lab/store-form-compile.ts(9,15): error TS2345: Argument of type 'DeepSignal<UserProfile>' is not assignable to parameter of type 'WritableSignal<unknown>'.
  Type 'DeepSignal<UserProfile>' is missing the following properties from type 'WritableSignal<unknown>': set, update, asReadonly, [ɵWRITABLE_SIGNAL]
```

So every write has to go through a method you declared in `withMethods`, **because `protectedState` defaults to `true`**. That is a default, not a law. `signalStore({ protectedState: false }, ...)` makes external `patchState` calls compile, and `unprotected(store)` from `@ngrx/signals/testing` opens a protected store on purpose in tests. Both are opt-ins you have to type deliberately, which is the point.

## The bridge is `linkedSignal`

The form needs something writable. The store gives you something readable. The piece between them is the `linkedSignal` from the harness, and this is what it buys you:

```typescript
// Same harness: store, wrapper, bridge, form.
f.name().value.set('Filip Franik');
f.bio().value.set('Bio goes here.');

probe('local-edits', {
  formName: f.name().value(),
  modelName: model().name,
  storeName: store.user.name(),        // untouched
  storeSaveCount: store.saveCount(),
  dirty: f().dirty(),
  valid: f().valid(),
});

expect(store.user.name()).toBe('Filip');
```

```text
[PROBE] local-edits :: {"formName":"Filip Franik","modelName":"Filip Franik","storeName":"Filip","storeSaveCount":0,"dirty":false,"valid":true}
```

That is the whole architecture. The user types into a local copy, and the store keeps its old value until something deliberately saves.

`storeName` is still `Filip`.

Now the `{ ...fromStore }` in the computation. I put the copy there because I assumed that without it the form would write straight into the store's own object. If that were true, every form in the app would be a hole in the store, so it is worth a probe. Here is the same bridge with the copy removed:

```typescript
// Same harness, different computation, and a bare form() with no schema.
const model = linkedSignal<UserProfile, UserProfile>({
  source: store.user,
  computation: (fromStore) => fromStore, // NO copy
});
const objectBefore = store.user();
const sameRef = model() === objectBefore;
const f = form(model);
let thrown: string | null = null;
try {
  f.name().value.set('No Copy');
} catch (e) {
  thrown = `${(e as Error).constructor.name}: ${(e as Error).message}`;
}
probe('no-copy-computation', {
  modelIsSameObjectAsStore: sameRef,
  threw: thrown,
  rawStoreObjectNameProperty: (objectBefore as any).name,
  storeNameAfterFormWrite: store.user.name(),
  storeStillSameObject: store.user() === objectBefore,
  modelStillSameObject: model() === objectBefore,
  formName: f.name().value(),
});
```

```text
[PROBE] no-copy-computation :: {"modelIsSameObjectAsStore":true,"threw":null,"rawStoreObjectNameProperty":"Filip","storeNameAfterFormWrite":"Filip","storeStillSameObject":true,"modelStillSameObject":false,"formName":"No Copy"}
```

I had it wrong. `modelIsSameObjectAsStore:true` says the form really is handed the store's own object. But the form wrote `No Copy` into it and `storeNameAfterFormWrite` is still `Filip`, with `storeStillSameObject:true`. **Signal Forms writes immutably.** It builds a new object and sets that, which is what `modelStillSameObject:false` is showing you. The object you handed it is never touched.

So the copy is not what stops the form from corrupting the store. The form was never going to.

The copy still earns its place, for the reason the `runtime-freeze` probe printed a section ago: the object is not frozen, and assigning to a property of it changes what the store returns. Without the spread, your model and your store state are the same object, and any code that mutates the model in place is writing to the store. One line buys you the guarantee that only `withMethods` can move the store.

## Trap 1: a server push types over your user

The bridge resets whenever the store changes, and the store changes for reasons that have nothing to do with the person at the keyboard.

```typescript
// Same harness: store, wrapper, bridge, form.
f.name().value.set('Half-typed na');
f.name().markAsTouched();
const beforePush = { name: f.name().value(), dirty: f().dirty(), touched: f.name().touched() };

// Something else patches the store - a websocket, a refresh, another component.
store.serverPush({ name: 'Server Name', email: 'server@example.com', bio: 'from the server' });

const afterPush = { name: f.name().value(), dirty: f().dirty(), touched: f.name().touched() };

probe('server-push-while-typing', { beforePush, afterPush });
```

```text
[PROBE] server-push-while-typing :: {"beforePush":{"name":"Half-typed na","dirty":false,"touched":true},"afterPush":{"name":"Server Name","dirty":false,"touched":true}}
```

`Half-typed na` became `Server Name` mid-sentence. The `touched` flag survived, which makes it worse: the field looks like the user visited it and typed that.

The fix lives in the computation, using `previous` to notice that the user has diverged from what the store last gave them. `previous.value` is what the bridge produced last time, and `previous.source` is the source value it produced it from. [Yesterday's post](https://www.pacyfist.dev/posts/angular-linkedsignal-vs-computed/) prints that whole object if you want to see it.

```typescript
// Same harness, different computation.
const model = linkedSignal<UserProfile, UserProfile>({
  source: store.user,
  computation: (fromStore, previous) => {
    // Only adopt the server value if the user has not started editing.
    if (previous && JSON.stringify(previous.value) !== JSON.stringify(previous.source)) {
      return previous.value;         // keep what the user typed
    }
    return { ...fromStore };
  },
});
const f = form(model, (path) => { required(path.name); });

f.name().value.set('Half-typed na');
const before = f.name().value();

store.serverPush({ name: 'Server Name', email: 'server@example.com', bio: 'from the server' });
const after = f.name().value();

probe('guarded-computation', { before, after });
```

```text
[PROBE] guarded-computation :: {"before":"Half-typed na","after":"Half-typed na"}
```

Half-typed text survives the push. `JSON.stringify` is fine for a flat profile object and wrong for anything big. The shape of the rule is what matters: compare `previous.value` against `previous.source`. If they differ, the user owns the field.

## Saving: `submit()` calls your store method

So far nothing has reached the store at all, which is only half an architecture. The bridge is worth building if saving is cheap, and `submit()` slots onto a store method with no ceremony:

```typescript
// Same harness, with an async body so it can await submit().
f.name().value.set('Submitted Name');
const countBefore = store.saveCount();

const ok = await submit(f, async (theForm) => {
  store.saveProfile(theForm().value());
  return undefined;
});

probe('submit-path', {
  submitResolved: ok,
  countBefore,
  countAfter: store.saveCount(),
  storeName: store.user.name(),
  formDirtyAfterSubmit: f().dirty(),
});
```

```text
[PROBE] submit-path :: {"submitResolved":true,"countBefore":0,"countAfter":1,"storeName":"Submitted Name","formDirtyAfterSubmit":false}
```

The store moved to `Submitted Name` and the save counter went up exactly once.

The last key needs a word, because the obvious reading of it is wrong. `formDirtyAfterSubmit:false` does not mean `submit()` tidied the form up afterwards. The form was never dirty in the first place, because `value.set()` does not make a field dirty. The last section of this post measures exactly that.

The other half of the saving question is what happens when the form is invalid. If `submit()` runs your store method anyway, every handler in the app needs a guard on its first line. The store plays no part in this one, so the model is a plain `signal`: what is being tested is `submit()`, not the bridge.

```typescript
const store = TestBed.inject(UserStore);

await TestBed.runInInjectionContext(async () => {
  const model = signal<UserProfile>({ name: '', email: 'not-an-email', bio: '' });
  const f = form(model, (path) => {
    required(path.name, { message: 'Name is required' });
    email(path.email, { message: 'Not an email' });
  });

  let actionRan = false;
  const ok = await submit(f, async () => { actionRan = true; return undefined; });

  probe('submit-invalid', {
    submitResolved: ok,
    actionRan,
    formValid: f().valid(),
    touchedAfterSubmit: f.name().touched(),
    errors: f.name().errors().map((e: any) => e.kind ?? e.message),
  });
});
```

```text
[PROBE] submit-invalid :: {"submitResolved":false,"actionRan":false,"formValid":false,"touchedAfterSubmit":true,"errors":["required"]}
```

`submit` returned `false` and your callback never fired. It also marked the offending field touched, so the error message appears. You do not need that guard.

## Trap 2: the auto-save loop is real

Now the pattern everybody wants: save as the user types, like a document editor. The obvious version is an `effect` that pushes the model into the store. I gave it a circuit breaker, because I wanted a number instead of a hung test:

```typescript
// Same harness, plus one more injection: const injector = TestBed.inject(Injector);
let effectRuns = 0;
const LIMIT = 25;
let trippedGuard = false;

// The "clever" auto-save: push every model change straight into the store.
effect(() => {
  const current = model();
  effectRuns++;
  if (effectRuns > LIMIT) { trippedGuard = true; return; }   // circuit breaker
  untracked(() => store.autoSave(current));
}, { injector });

TestBed.tick();                       // flush effects: the test is zoneless
const afterInit = effectRuns;

f.name().value.set('Typing');
TestBed.tick();

probe('auto-save-loop', {
  afterInit,
  effectRunsAfterOneKeystroke: effectRuns,
  guardTripped: trippedGuard,
  storeSaveCount: store.saveCount(),
});
```

```text
[PROBE] auto-save-loop :: {"afterInit":26,"effectRunsAfterOneKeystroke":27,"guardTripped":true,"storeSaveCount":25}
```

Twenty-six effect runs and twenty-five store writes before a single keystroke. The guard was the only thing that stopped it.

Without the guard the effect never comes back at all. The lab keeps a copy of that same test with the `if (effectRuns > LIMIT)` line deleted, and running the suite with it enabled looks like this:

```bash
timeout 90 npx ng test --watch=false --reporters=verbose > noguard.log 2>&1
echo "exit code: $?"
grep -c "no-circuit-breaker" noguard.log
```

```text
exit code: 124
0
```

`124` is what `timeout` returns when it kills the process, and `0` is how many probe lines the un-guarded test managed to print. Ninety seconds in, `TestBed.tick()` had still not returned, nothing had thrown, and no test timeout had fired. That is the failure mode: not a crash, just a run that never ends.

The loop is easy to see once you write the cycle down:

1. The effect reads `model()` and calls `autoSave`.
2. `autoSave` patches `store.user` with a **new object**.
3. `store.user` is the `linkedSignal` source, so the computation re-runs and produces another new object.
4. The model changed, so the effect runs again. Go to 1.

No step in that list is a mistake on its own. The loop exists because every hop makes a **new object**, and signals compare objects by identity, not by contents.

## The fix is one option, in one place

The option is `equal`, and it is the same option that saves stale selections in [yesterday's `linkedSignal` post](https://www.pacyfist.dev/posts/angular-linkedsignal-vs-computed/). It is not the same fix, and it does not go in the same place. Getting those two mixed up is easy, so here is the difference in plain terms.

**Put `equal` on the source signal to stop a reset.** That is yesterday's problem: a refresh hands the source a new but identical array, the `linkedSignal` sees a new source value, and it throws the user's selection away. Teaching the source what "changed" means keeps the recomputation from happening at all.

**Put `equal` on the `linkedSignal` itself to stop a notification.** That is this post's problem. It does not stop the bridge from recomputing when the store patches, and it does not stop a reset. It stops the bridge from telling anything downstream that its value moved when the recomputed profile matches the old one, and the downstream effect is what was looping. Here, `store.user` belongs to the store, so the bridge is the only end of the wire I get to configure anyway.

```typescript
const sameProfile = (a: UserProfile, b: UserProfile) =>
  a.name === b.name && a.email === b.email && a.bio === b.bio;

const model = linkedSignal<UserProfile, UserProfile>({
  source: store.user,
  computation: (fromStore) => ({ ...fromStore }),
  equal: sameProfile,
});
```

The rest of that test is the previous one line for line, except the probe also prints the store's final name:

```typescript
probe('auto-save-loop-guarded', {
  afterInit,
  effectRunsAfterOneKeystroke: effectRuns,
  guardTripped: trippedGuard,
  storeSaveCount: store.saveCount(),
  storeName: store.user.name(),
});
```

```text
[PROBE] auto-save-loop-guarded :: {"afterInit":1,"effectRunsAfterOneKeystroke":2,"guardTripped":false,"storeSaveCount":2,"storeName":"Typing"}
```

One run at startup, one more per keystroke, no runaway, and the store still ends up saying `Typing`. **Twenty-five wasted writes became zero by adding an `equal` comparator.**

In a real app you would still put a `debounceTime` in front of the network call, using an `rxMethod` in the store. But debouncing a loop only slows the loop down. Fix the identity first, then debounce.

## `reset()` does not put the store's value back

One more trap, and it is the one that shows up after a failed save. The save fails, you want the form back the way the store has it, and `reset()` is sitting right there. It does not do that, and along the way it shows what `dirty` really means:

```typescript
// Same harness: store, wrapper, bridge, form.
const atStart = f.name().dirty();
f.name().value.set('Programmatic');
const afterValueSet = f.name().dirty();
f.name().markAsDirty();
const afterMarkAsDirty = f.name().dirty();
f().reset();
const afterReset = { dirty: f.name().dirty(), value: f.name().value() };

probe('dirty-semantics', { atStart, afterValueSet, afterMarkAsDirty, afterReset });
```

```text
[PROBE] dirty-semantics :: {"atStart":false,"afterValueSet":false,"afterMarkAsDirty":true,"afterReset":{"dirty":false,"value":"Programmatic"}}
```

One probe line, and both halves of it surprised me.

Writing through `value.set()` left `dirty` false, so `dirty` tracks user interaction rather than value changes. The Angular guide says `dirty()` becomes true when a value is modified, which is worth knowing precisely: a programmatic `value.set()` does not count. Only a change coming through the UI, or an explicit `markAsDirty()`, does.

And `reset()` cleared the flags but left the **value** exactly where it was. The store still says `Filip`, the form still says `Programmatic`. The doc comment on `reset` is blunt about it: "Resets the `touched` and `dirty` state of the field and its descendants. Note this does not change the data model." So if you were counting on `reset()` to restore the store's data, it will not, unless you hand it the data. The signature is `reset(value?: TValue)`, and the same comment describes the parameter as "Optional value to set to the form. If not passed, the value will not be changed." `f().reset(store.user())` puts you back where the store is.

## Summary

* **`form()` needs a `WritableSignal` and SignalStore gives you a `DeepSignal`.** All three `form()` overloads want the same first parameter, so `form(store.user)` fails with TS2345 whichever one you reach for.
* **The store's immutability is compile-time only.** One `as any` and `store.user.set(...)` rewrote the state, and the state object is not even frozen in dev mode.
* **`patchState` from outside the store does not compile** while `protectedState` keeps its default of `true`. `protectedState: false` and `unprotected()` are the deliberate ways out.
* **Bridge the two with a `linkedSignal`** that copies the store value. Edits stay local until you save, and the copy keeps your model and your store state from being the same object.
* **A store update mid-typing overwrites the user.** Compare `previous.value` with `previous.source` in the computation and keep the user's version when they differ.
* **`submit()` skips the action entirely on an invalid form** and marks fields touched for you.
* **The naive auto-save effect really does loop**: 26 runs and 25 store writes before one keystroke, and a test run that never finishes if you delete the circuit breaker. Adding `equal` to the bridge took it to 1.
* **`equal` goes on the source to stop a reset, and on the `linkedSignal` to stop a notification.** Two different fixes for two different problems.
* **`dirty` is about interaction, not values**, and `reset()` does not restore the old value unless you pass it one.

One last thing to try before you ship this: open two browser tabs on the same form and type in one of them. Whatever your store does to the other tab is exactly what it will do to a real user the first time a websocket message lands.
