---
# SEO Target Queries:
#   Google: "angular signal forms ngrx signalstore", "angular signal store and forms", "signal forms writable signal"
#   Bing:   "angular signal store form", "ngrx signalstore signal forms", "angular signal store best practices"
tags: ["typescript", "angular", "signal forms", "ngrx", "signalstore"]
categories: ["typescript", "angular"]
title: "Signal Forms + NgRx SignalStore: The Missing Bridge"
image:
  path: /assets/img/2026-08-20/main.jpg
  alt: Two pieces that refuse to click together until something sits between them.
published: false
---

The [Signal Forms post](https://www.pacyfist.dev/posts/angular-signal-forms-14-awkward-questions-and-one-nasty-surprise/) ended with a signup form built out of a plain `signal()` and a schema, and it worked beautifully. The obvious next question is what happens when that data lives in an NgRx SignalStore instead of a component field.

The answer is short. `form(store.user)` does not compile, and it is not close.

So I built the lab: Angular 22 with `@ngrx/signals` 22, a real store, a real form, and a test that prints what actually happens for every case I could think of. Two of the results are traps I would have shipped.

## The lab

```bash
npm install @ngrx/signals@22 @ngrx/operators
npx ng version
```

```text
Angular CLI       : 22.1.6
Angular           : 22.1.3
Node.js           : 26.5.0
Package Manager   : npm 11.17.0
Operating System  : linux x64
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

And the probe helper, so every log line traces back to code:

```typescript
function probe(label: string, payload: unknown) {
  console.log(`[PROBE] ${label} :: ${JSON.stringify(payload)}`);
}
```

## Why they refuse to connect

`form()` has exactly one shape in Angular 22, and the type definition is blunt about it:

```typescript
declare function form<TModel>(model: WritableSignal<TModel>): FieldTree<TModel>;
```

The doc comment above it explains why:

> `form` uses the given model as the source of truth and *does not* maintain its own copy of the data. This means that updating the value on a `FieldState` updates the originally passed in model as well.

A Signal Form does not hold your data. It writes straight back into the signal you handed it. So it needs a `WritableSignal`, and a SignalStore hands you the opposite. Here is the whole question in one file:

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

```bash
npx tsc --noEmit -p tsconfig.app.json
```

```text
src/app/lab/store-form-compile.ts(9,15): error TS2345: Argument of type 'DeepSignal<UserProfile>' is not assignable to parameter of type 'WritableSignal<unknown>'.
  Type 'DeepSignal<UserProfile>' is missing the following properties from type 'WritableSignal<unknown>': set, update, asReadonly, [ɵWRITABLE_SIGNAL]
```

`DeepSignal` is the nice part of SignalStore: every property of your state is its own signal, so `store.user.name` is a signal too, and a template reading `store.user.name()` does not re-render when `bio` changes.

```typescript
const store = TestBed.inject(UserStore);
probe('store-signal-shape', {
  userIsFunction: typeof store.user === 'function',
  userHasSet: 'set' in store.user,
  nameIsFunction: typeof store.user.name === 'function',
  nameHasSet: 'set' in store.user.name,
  nameValue: store.user.name(),
});
```

```text
[PROBE] store-signal-shape :: {"userIsFunction":true,"userHasSet":true,"nameIsFunction":true,"nameHasSet":false,"nameValue":"Filip"}
```

Look at `userHasSet: true`. That is not a typo, and it leads somewhere uncomfortable.

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

The compiler does defend the front door properly, though. Calling `patchState` from a component does not compile in `@ngrx/signals` 22:

```typescript
patchState(store, { user: current });
```

```text
✘ [ERROR] TS2345: Argument of type '{ user: DeepSignal<UserProfile>; isSaving: Signal<boolean>; ... } & StateSource<...>'
  is not assignable to parameter of type 'WritableStateSource<{ user: UserProfile; isSaving: boolean; saveCount: number; }>'.
  The types of '[STATE_SOURCE].user' are incompatible between these types.
    Type 'Signal<UserProfile>' is missing the following properties from type 'WritableSignal<UserProfile>': set, update, asReadonly, [ɵWRITABLE_SIGNAL]
```

Every write has to go through a method you declared in `withMethods`. That is the design, and it is a good one.

## The bridge is `linkedSignal`

The form needs something writable. The store gives you something readable. The piece between them is a `linkedSignal`:

```typescript
const model = linkedSignal<UserProfile, UserProfile>({
  source: store.user,
  computation: (fromStore) => ({ ...fromStore }),
});

const f = form(model, (path) => {
  required(path.name, { message: 'Name is required' });
  email(path.email, { message: 'Not an email' });
});

f.name().value.set('Filip Franik');
f.bio().value.set('Writes blog posts at 1am.');

probe('local-edits', {
  formName: f.name().value(),
  modelName: model().name,
  storeName: store.user.name(),        // untouched
  storeSaveCount: store.saveCount(),
  dirty: f().dirty(),
  valid: f().valid(),
});
```

```text
[PROBE] local-edits :: {"formName":"Filip Franik","modelName":"Filip Franik","storeName":"Filip","storeSaveCount":0,"dirty":false,"valid":true}
```

That is the whole architecture. The user types into a local copy. The store keeps its old value until something deliberately saves. `storeName` is still `Filip`.

Note the `{ ...fromStore }` in the computation. Without the copy you hand the form the store's own object and the form writes into it directly, which is the thing we are trying to avoid.

## Trap 1: a server push types over your user

The bridge resets whenever the store changes, and the store changes for reasons that have nothing to do with the person at the keyboard.

```typescript
const f = form(model, (path) => { required(path.name); });

f.name().value.set('Half-typed na');
f.name().markAsTouched();
const beforePush = { name: f.name().value(), dirty: f().dirty(), touched: f.name().touched() };

// Something else patches the store - a websocket, a refresh, another component.
store.serverPush({ name: 'Server Name', email: 'server@example.com', bio: 'from the server' });

const afterPush = { name: f.name().value(), dirty: f().dirty(), touched: f.name().touched() };

probe('server-push-while-typing', { beforePush, afterPush });
```

```text
[PROBE] server-push-while-typing :: {"beforePush":{"name":"Half-typed na","dirty":false,"touched":true},
"afterPush":{"name":"Server Name","dirty":false,"touched":true}}
```

`Half-typed na` became `Server Name` mid-sentence. The `touched` flag survived, which makes it worse: the field looks like the user visited it and typed that.

The fix lives in the computation, using `previous` to notice that the user has diverged from what the store last gave them:

```typescript
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

f.name().value.set('Half-typed na');
const before = f.name().value();

store.serverPush({ name: 'Server Name', email: 'server@example.com', bio: 'from the server' });
const after = f.name().value();

probe('guarded-computation', { before, after });
```

```text
[PROBE] guarded-computation :: {"before":"Half-typed na","after":"Half-typed na"}
```

Half-typed text survives the push. `JSON.stringify` is fine for a flat profile object and is the wrong tool for anything big, but the shape of the rule is what matters: compare `previous.value` against `previous.source`, and if they differ, the user owns the field.

## Saving: `submit()` calls your store method

Signal Forms ship a `submit()` helper, and it slots onto a store method with no ceremony:

```typescript
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

It also refuses to run the action at all when the form is invalid, and marks the offending fields touched so the errors appear:

```typescript
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
```

```text
[PROBE] submit-invalid :: {"submitResolved":false,"actionRan":false,"formValid":false,"touchedAfterSubmit":true,"errors":["required"]}
```

`submit` returned `false` and your callback never fired. You do not need an `if (form.invalid) return;` guard at the top of your handler.

## Trap 2: the auto-save loop is real

Now the pattern everybody wants: save as the user types, like a document editor. The obvious version is an `effect` that pushes the model into the store. I gave it a circuit breaker, because I wanted a number instead of a hung test:

```typescript
const model = linkedSignal<UserProfile, UserProfile>({
  source: store.user,
  computation: (fromStore) => ({ ...fromStore }),
});
const f = form(model);

let effectRuns = 0;
const LIMIT = 25;
let trippedGuard = false;

effect(() => {
  const current = model();
  effectRuns++;
  if (effectRuns > LIMIT) { trippedGuard = true; return; }   // circuit breaker
  untracked(() => store.autoSave(current));
}, { injector });

TestBed.tick();
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

Twenty-six effect runs and twenty-five store writes before a single keystroke. The guard was the only thing that stopped it. The first version of this test, written without the guard, hung my test run until I killed it.

The loop is easy to see once you write the cycle down:

1. The effect reads `model()` and calls `autoSave`.
2. `autoSave` patches `store.user` with a **new object**.
3. `store.user` is the `linkedSignal` source, so the computation re-runs and produces another new object.
4. The model changed, so the effect runs again. Go to 1.

Nothing here is wrong on its own. The cycle exists because every hop creates a new object reference, and signals compare references.

## The fix is one option, in one place

Same trick that fixes stale selections in `linkedSignal`: tell the bridge what "changed" means.

```typescript
const sameProfile = (a: UserProfile, b: UserProfile) =>
  a.name === b.name && a.email === b.email && a.bio === b.bio;

const model = linkedSignal<UserProfile, UserProfile>({
  source: store.user,
  computation: (fromStore) => ({ ...fromStore }),
  equal: sameProfile,
});
```

Everything else in the test stayed identical:

```text
[PROBE] auto-save-loop-guarded :: {"afterInit":1,"effectRunsAfterOneKeystroke":2,"guardTripped":false,"storeSaveCount":2,"storeName":"Typing"}
```

One run at startup, one more per keystroke, no runaway, and the store still ends up saying `Typing`. **Twenty-five wasted writes became zero by adding an `equal` comparator.**

In a real app you would still put a `debounceTime` in front of the network call, using an `rxMethod` in the store. But debouncing a loop only slows the loop down. Fix the identity first, then debounce.

## One more thing about `dirty`

I expected setting a value to mark the field dirty. It does not:

```typescript
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

Two surprises in one line. Writing through `value.set()` leaves `dirty` false, so `dirty` tracks user interaction rather than value changes. And `reset()` clears the flags but leaves the **value** exactly where it was. If you were counting on `reset()` to restore the original data, it will not.

## Summary

* **`form()` needs a `WritableSignal` and SignalStore gives you a `DeepSignal`.** `form(store.user)` fails with TS2345. There is no clever way around it, and you would not want one.
* **The store's immutability is compile-time only.** One `as any` and `store.user.set(...)` rewrote the state with no error.
* **`patchState` from a component does not compile** in `@ngrx/signals` 22. Writes go through `withMethods`.
* **Bridge the two with a `linkedSignal`** that copies the store value. Edits stay local until you save.
* **A store update mid-typing overwrites the user.** Compare `previous.value` with `previous.source` in the computation and keep the user's version when they differ.
* **`submit()` skips the action entirely on an invalid form** and marks fields touched for you.
* **The naive auto-save effect really does loop**: 26 runs and 25 store writes before one keystroke. Adding `equal` to the bridge took it to 1.
* **`dirty` is about interaction, not values**, and `reset()` does not restore the old value.

Friendly closing tip: whichever pattern you pick, open two browser tabs on the same form and type in one of them. Whatever your store does to the other tab is exactly what it will do to a real user the first time a websocket message lands.
