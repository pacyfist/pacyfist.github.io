---
tags: ["typescript", "angular", "signals", "rxresource", "tosignal"]
categories: ["typescript", "angular"]
title: "Angular rxResource vs toSignal: A Fair Test"
image:
  path: /assets/img/2026-08-26/main.jpg
  alt: Two measuring tapes arguing over one HTTP request.
---

The endpoint was `/api/users/bad`, and my test had a very satisfying red 500 in it.
Then I changed the user ID to `/api/users/good` and discovered that the screen never recovered. The failed request had killed the Observable that was supposed to watch the ID.

That bug raises an awkward question: should this screen use `rxResource` or `toSignal`?

Both return signals. Both can subscribe to an HTTP Observable. But they do not solve the same-sized problem. **`toSignal` adapts an Observable. `rxResource` adds a request state machine around one.**

I built the same user lookup both ways, then tested parameter changes, loading, multiple emissions, errors, recovery, fallback values, reloads, overlapping requests, completion, and cleanup.

## The lab

I created a throwaway Angular workspace for these experiments:

```bash
npx --yes @angular/cli@22.2.0 new rxresource-lab \
  --style=css --ssr=false --zoneless --defaults --skip-git
```

The CLI created the project and installed its packages successfully. Here are the versions it actually installed:

```bash
npx ng version
```

```text
Angular CLI       : 22.2.0
Angular           : 22.2.0
Node.js           : 26.5.0
Package Manager   : npm 11.17.0
Operating System  : linux x64

@angular/build            22.2.0
@angular/core             22.2.0
rxjs                      7.8.2
typescript                6.0.3
vitest                    4.1.11
```

Every asynchronous source in the tests is controlled. It counts subscriptions and unsubscriptions, and the test decides exactly when it emits, fails, or completes:

```typescript
function controlled<T>() {
  const subject = new Subject<T>();
  let subscriptions = 0;
  let unsubscriptions = 0;

  return {
    observable: new Observable<T>((subscriber) => {
      subscriptions++;
      const subscription = subject.subscribe(subscriber);

      return () => {
        unsubscriptions++;
        subscription.unsubscribe();
      };
    }),
    next: (value: T) => subject.next(value),
    error: (error: unknown) => subject.error(error),
    complete: () => subject.complete(),
    subscriptions: () => subscriptions,
    unsubscriptions: () => unsubscriptions,
  };
}
```

There are no wall-clock sleeps and no real server. Both implementations receive the same trigger sequence.

I ran the whole suite in one process:

```bash
npx ng test --watch=false --reporters=verbose
```

```text
Test Files  1 passed (1)
     Tests  8 passed (8)
  Duration  1.23s
```

The log lines in the experiments below came from that run.

## Four things that look similar

The first version converts one existing Observable:

```typescript
const user = toSignal(http.get<User>('/api/users/a'));
```

This is what `toSignal` is designed to do. Angular subscribes immediately, stores the latest emission, and exposes it through a signal.

It is not reactive to a separate ID signal. This code reads `id()` once while building the URL:

```typescript
const id = signal('a');
const user = toSignal(http.get<User>(`/api/users/${id()}`));

id.set('b'); // does not create another HTTP Observable
```

To make the lookup reactive, the ID has to become part of the Observable pipeline:

```typescript
const user = toSignal(
  toObservable(id).pipe(
    switchMap((value) => http.get<User>(`/api/users/${value}`)),
  ),
);
```

If the screen also needs explicit loading and error states, those belong in the emitted value:

```typescript
type UserState =
  | { kind: 'loading' }
  | { kind: 'value'; value: User }
  | { kind: 'error'; error: HttpErrorResponse };

const user = toSignal(
  toObservable(id).pipe(
    switchMap((value) =>
      http.get<User>(`/api/users/${value}`).pipe(
        map((user): UserState => ({ kind: 'value', value: user })),
        catchError((error: HttpErrorResponse) =>
          of<UserState>({ kind: 'error', error }),
        ),
        startWith<UserState>({ kind: 'loading' }),
      ),
    ),
  ),
  { initialValue: { kind: 'loading' } as UserState },
);
```

The `rxResource` version puts those concerns in its API:

```typescript
const user = rxResource({
  params: () => id(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
});
```

The fair comparison is not bare `toSignal` versus `rxResource`. It is the complete RxJS state pipeline versus `rxResource`.

## Experiment 1: changing the user ID

The test started all three versions with ID `a`, changed it to `b`, then completed the two reactive requests.

```text
[EXP] reactive-params :: {
  "rawSubscriptions":1,
  "reactiveKeys":["a","b"],
  "resourceKeys":["a","b"],
  "reactiveCancelledA":1,
  "resourceCancelledA":1,
  "reactiveValue":{"id":"b","name":"Reactive B"},
  "resourceValue":{"id":"b","name":"Resource B"}
}
```

The bare conversion subscribed once. Both reactive implementations requested `a`, cancelled it when the ID changed, and requested `b`.

**`toSignal` does not choose reactivity for you.** Once `toObservable(id)` and `switchMap` describe that behavior, it works exactly as requested.

`rxResource` makes this particular behavior shorter because reactive parameters are part of the resource contract.

## Experiment 2: loading, streaming, and completion

Neither controlled Observable emitted immediately. Then both emitted `one`, emitted `two`, and completed.

```text
[EXP] loading-stream-completion :: {
  "initial":{
    "resourceStatus":"loading",
    "resourceIsLoading":true,
    "resourceHasValue":false
  },
  "first":{
    "toSignal":"one",
    "resource":"one",
    "resourceStatus":"resolved"
  },
  "second":{
    "toSignal":"two",
    "resource":"two",
    "resourceStatus":"resolved"
  },
  "afterCompletion":{
    "toSignal":"two",
    "resource":"two",
    "resourceStatus":"resolved"
  }
}
```

The missing `toSignal` field in `initial` is deliberate. `JSON.stringify` omits object properties whose value is `undefined`. Without an `initialValue`, that is what `toSignal` returns before the first emission.

`rxResource` exposed a separate loading state. After the first value, both followed later emissions and both kept the last value after completion.

That last part matters. Despite the name, **`rxResource.stream` is not limited to one HTTP response.** It can track an Observable that emits more than once.

## Experiment 3: errors and recovery

I tested four versions together:

- bare `toSignal` receiving an Observable error;
- `toSignal` with a tagged `UserState` and `catchError` inside `switchMap`;
- `toSignal` with `catchError` outside `switchMap`;
- `rxResource` receiving the same error through its stream.

All four received the same `HttpErrorResponse` object. Then the ID changed from `bad` to `good`.

```text
[EXP] error-and-recovery :: {
  "afterError":{
    "bareThrowsSameObject":true,
    "stateKind":"error",
    "outerCatchValue":null,
    "resourceStatus":"error",
    "resourceErrorSameObject":true,
    "resourceValueThrows":true
  },
  "newStateRequest":true,
  "newOuterCatchRequest":false,
  "newResourceRequest":true,
  "outerCatchValueAfterRecovery":null,
  "stateAfterRecovery":"value",
  "resourceAfterRecovery":"resolved"
}
```

The bare signal threw the original `HttpErrorResponse` when read. That is the documented `toSignal` behavior.

The tagged-state version emitted `{ kind: 'error' }`. The resource changed to `error` and returned the same object from `error()`.

Both complete implementations recovered when the ID changed. The important bit in the RxJS version is where `catchError` lives:

```typescript
toObservable(id).pipe(
  switchMap((value) =>
    http.get<User>(`/api/users/${value}`).pipe(
      catchError((error) => of({ kind: 'error', error })),
    ),
  ),
);
```

The inner request is allowed to end. The outer Observable keeps watching the ID.

The test included that outer placement too. It returned `null`, created no request for `good`, and stayed `null`. The replacement value completed the whole chain after the first failure. There was nothing left to hear the next ID.

## Experiment 4: a fallback is a successful value

What if the stream catches a 404 and returns `null`?

```typescript
const user = rxResource<User | null, void>({
  stream: () => http.get<User>('/api/users/missing').pipe(
    catchError(() => of(null)),
  ),
});
```

Here is the result:

```text
[EXP] fallback-null :: {
  "status":"resolved",
  "value":null,
  "hasValue":true
}
```

That is not `rxResource` hiding an error. The Observable did not error. `catchError` replaced the failure with a normal `null` emission, so the resource resolved with that value.

This can be a good policy when “missing” is a normal answer. It is a bad policy when the UI must distinguish an empty result from a broken server.

Completing without any value produces a different result:

```typescript
const user = rxResource<User, void>({
  stream: () => EMPTY,
});
```

```text
[EXP] empty-completion :: {
  "status":"error",
  "errorName":"Error",
  "errorMessage":"NG0991: Resource completed before producing a value",
  "hasValue":false
}
```

If an HTTP error was converted to `EMPTY`, the original HTTP details are already gone. The resource can only report that its stream completed without producing a value.

## Experiment 5: reload while busy

`rxResource` has a method for rerunning the same request:

```typescript
user.reload();
```

The return value is easy to ignore, so the test checked it during initial loading, after success, and while the reload was still running.

```text
[EXP] reload-policy :: {
  "reloadWhileInitialLoading":false,
  "duringReload":{
    "returned":true,
    "status":"reloading",
    "isLoading":true,
    "value":{"id":"a","name":"Ada"},
    "requestCount":2
  },
  "reloadWhileReloading":false,
  "requestCountAfterSecondReload":2
}
```

In Angular 22.2.0, reload was refused while the resource was already busy. It returned `false` and did not create another subscription.

After the first value resolved, reload returned `true`. The resource entered `reloading`, kept Ada available, and started one new subscription.

**Use `isLoading()` for a spinner that covers both first load and reload.** Use the boolean return when the caller needs to know whether a reload actually started.

## Experiment 6: polling is an operator decision

A refresh signal or timer still needs a concurrency policy. I sent three triggers before any request completed and tested three RxJS operators.

```text
[EXP] flattening-policy :: {
  "switchMap":{
    "beforeCompletion":{"requestCount":3,"cancellations":2},
    "values":[30],
    "finalRequestCount":3
  },
  "exhaustMap":{
    "beforeCompletion":{"requestCount":1,"cancellations":0},
    "values":[30],
    "finalRequestCount":1
  },
  "concatMap":{
    "beforeCompletion":{"requestCount":1,"cancellations":0},
    "values":[30,20],
    "finalRequestCount":3
  }
}
```

The policies are different on purpose:

- `switchMap` started all three and cancelled the first two. The latest trigger won.
- `exhaustMap` ignored triggers while the first request was active. The active request won.
- `concatMap` queued the extra triggers. Every trigger eventually got a request.

None of this behavior belongs to `toSignal`. It belongs to the Observable passed into it.

`rxResource.reload()` behaves closest to the no-overlap case in this test: while busy, another reload returned `false`. The useful question is not “which poller wins?” It is **whether stale work should be cancelled, ignored, or queued**.

## Experiment 7: cleanup

Finally, I destroyed the Angular injection context while both APIs had an active subscription.

```text
[EXP] teardown :: {
  "destroyRefWasPresent":true,
  "toSignalUnsubscriptions":1,
  "resourceUnsubscriptions":1
}
```

Both unsubscribed exactly once.

If a timer lives inside the Observable passed to `toSignal`, that unsubscription also tears down the timer. If application code creates a separate `setInterval` that calls `resource.reload()`, application code must clear that interval. The owner of the timer owns its cleanup.

## Request gating: pausing with undefined

In real screens, a lookup key is rarely ready on frame one. Maybe the user has not clicked an account in a list yet, or a dialog opened without an active ID.

If you pass `undefined` from `params`, `rxResource` halts automatically:

```typescript
const selectedId = signal<string | undefined>(undefined);

const user = rxResource({
  params: () => selectedId(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
});
```

When `params` returns `undefined`, `rxResource` enters the `'idle'` status. It does not call `stream`, and `isLoading()` stays `false`.

As soon as `selectedId.set('42')` runs, the status switches to `'loading'` and the HTTP request fires. If `selectedId` later resets to `undefined`, any pending request cancels and the resource goes straight back to `'idle'`.

Handling that with `toSignal` requires extra plumbing:

```typescript
const user = toSignal(
  toObservable(selectedId).pipe(
    filter((id): id is string => id !== undefined),
    switchMap((id) => http.get<User>(`/api/users/${id}`)),
  ),
);
```

That halts the initial request. But when `selectedId` resets to `undefined`, `filter` simply drops the event. The signal keeps showing the previous user, because an Observable stream has no concept of an `'idle'` status unless you wrap every emission in a custom state object.

## Debouncing and concurrency

Typeahead search brings up another subtle difference: where timing logic belongs.

With `toSignal`, debouncing is just an operator in the chain:

```typescript
const search = toSignal(
  toObservable(query).pipe(
    debounceTime(300),
    distinctUntilChanged(),
    switchMap((term) => http.get<SearchResult[]>(`/api/search?q=${term}`)),
  ),
  { initialValue: [] },
);
```

The 300 ms pause sits comfortably between the input stream and `switchMap`.

You cannot put `debounceTime` inside `rxResource.stream` and get the same clean result:

```typescript
// Do not do this
const search = rxResource({
  params: () => query(),
  stream: ({ params }) =>
    of(params).pipe(
      debounceTime(300),
      switchMap((term) => http.get<SearchResult[]>(`/api/search?q=${term}`)),
    ),
});
```

Because `query()` changes on every keystroke, `params` re-runs immediately. `rxResource` cancels the old stream, sets `isLoading()` to `true`, and spawns a new stream. You churn the resource lifecycle on every letter.

With `rxResource`, debouncing must happen before the signal enters `params`:

```typescript
const debouncedQuery = toSignal(
  toObservable(query).pipe(
    debounceTime(300),
    distinctUntilChanged(),
  ),
  { initialValue: query() },
);

const search = rxResource({
  params: () => debouncedQuery(),
  stream: ({ params }) => http.get<SearchResult[]>(`/api/search?q=${params}`),
});
```

Now `params` only wakes up when the user stops typing. In `toSignal`, debouncing is a stream operator. In `rxResource`, debouncing belongs to the signal producer feeding `params`.

## Local mutations and optimistic updates

Read-only screens are simple. Editable screens are where data fetching tools usually get painful.

Suppose a user edits their name in an input. You want an optimistic update: change the UI immediately, send the HTTP PATCH in the background, and roll back if the server complains.

A signal created with `toSignal` is strictly read-only:

```typescript
const user = toSignal(http.get<User>('/api/user/1'));

// TypeScript error: Property 'update' does not exist on type 'Signal<User | undefined>'
user.update((prev) => ({ ...prev, name: 'Grace Hopper' }));
```

To support local mutations with `toSignal`, you have to wire up an action Subject, merge it into the Observable pipeline, and manage the cached state yourself.

`rxResource` handles this out of the box because `ResourceRef.value` is a `WritableSignal`:

```typescript
function renameUser(newName: string) {
  const current = user.value();
  if (!current) return;

  // 1. Update the UI immediately
  user.value.update((u) => (u ? { ...u, name: newName } : u));

  // 2. Persist to the server
  http.patch(`/api/users/${current.id}`, { name: newName }).subscribe({
    error: () => {
      // 3. Revert to server truth on failure
      user.reload();
    },
  });
}
```

You can call `.set()` or `.update()` directly on `user.value`. If the network request fails, one call to `user.reload()` restores the truth from the server.

## Reading a resource safely

`rxResource` exposes rich state, but templates often hide two common production bugs: null crashes and invisible reloads.

Here is the fragile pattern many developers write first:

{% raw %}

```html
<!-- Fragile: crashes on null fallbacks and hides reload spinners -->
@if (user.hasValue()) {
  <h2>{{ user.value().name }}</h2>
} @else if (user.error(); as error) {
  <p role="alert">Could not load the user: {{ error.message }}</p>
} @else if (user.isLoading()) {
  <p>Loading...</p>
}
```

{% endraw %}

That snippet has two traps:

1. **Null fallbacks crash the template.** If your stream catches a 404 and emits `null`, `hasValue()` is `true`. Reading `user.value().name` throws a `TypeError` at runtime.
2. **`hasValue()` shadows `isLoading()`.** During `user.reload()`, `hasValue()` stays `true`. Because it sits at the top of the `@if` ladder, the reload spinner is completely ignored.

Moving `isLoading()` to the very top causes a destructive reload: existing data disappears and the whole screen flips back to a loading spinner.

Here is the safe template pattern:

{% raw %}

```html
@if (user.error(); as error) {
  <p role="alert">Could not load the user: {{ error.message }}</p>
} @else if (user.hasValue()) {
  @if (user.value(); as u) {
    <h2>{{ u.name }}</h2>
  } @else {
    <p>User not found.</p>
  }

  @if (user.isLoading()) {
    <span class="badge">Refreshing...</span>
  }
} @else if (user.isLoading()) {
  <p>Loading...</p>
}
```

{% endraw %}

This template handles every state cleanly:

- If the server errors, the alert shows.
- If data exists, it checks `user.value(); as u`. A `null` fallback safely renders the not-found message instead of throwing.
- If a reload is active, `user.isLoading()` displays a non-destructive badge without tearing down the existing screen.
- If no data has loaded yet and the request is in flight, the initial `<p>Loading...</p>` block displays.

## Which one should you use?

Use `rxResource` when the thing you are building really is a managed resource:

- a reactive request identity with request gating (`undefined` sets status to `'idle'`);
- built-in loading and non-destructive reloading states;
- an error channel with automatic recovery;
- manual reload triggers;
- optimistic UI updates and local mutations via its writable `value` signal.

Those behaviors arrive as one consistent contract without writing custom state unions.

Use `toSignal` when you already have an Observable and want its latest value as a signal. It is especially natural for:

- store selectors, router streams, and WebSockets;
- pipelines where RxJS operators like `debounceTime`, `retry`, or `filter` define the core behavior;
- strictly read-only signal projections.

There is also a strong `toSignal` case for synchronous sources:

```typescript
const user = toSignal(userBehaviorSubject, { requireSync: true });
```

That returns `Signal<User>` rather than `Signal<User | undefined>`. No request state machine is needed because this is an Observable adaptation problem, not a loading problem.

If your `toSignal` pipeline is growing custom `{ loading, value, error }` types, reload subjects, and optimistic update buffers, you are reinventing a resource. That can be exactly the custom flexibility you need. If it is not, `rxResource` already built that state machine for you.

## Summary

- **`toSignal` adapts an Observable; `rxResource` models a resource.**
- **Compare complete implementations.** A tagged RxJS state pipeline can display errors and recover just as the resource can.
- **Reactive parameters are explicit with `toSignal`** and built into `rxResource`.
- **Request gating is native to `rxResource`.** Returning `undefined` from `params` halts requests and switches status to `'idle'`.
- **Debouncing belongs in different spots.** In `toSignal` it is an operator in the stream; in `rxResource` it belongs to the signal feeding `params`.
- **`ResourceRef.value` is writable.** You can `.set()` or `.update()` it for optimistic updates, while `toSignal` is strictly read-only.
- **A fallback value is a success value.** Returning `null` consumes the error for both approaches.
- **Reload keeps the old resource value visible**, and Angular 22.2.0 refuses another reload while busy.
- **Guard templates against null and reload shadowing.** Handle `null` fallbacks safely, and show non-destructive indicators while reloading.
- **Both APIs clean up their subscriptions** when their injection context is destroyed.

My friendly rule is simple: choose the abstraction whose input matches what you already have. An Observable belongs naturally in `toSignal`. A request with a lifecycle belongs naturally in `rxResource`.

## Resources

- [Angular rxResource Implementation Source Code](https://github.com/angular/angular/blob/5d3bc743d254092dd423dfb8790a7bb150deb03a/packages/core/rxjs-interop/src/rx_resource.ts#L62) - The core Angular 22 source code adapting RxJS streams to the resource state machine.
- [Angular toSignal Implementation Source Code](https://github.com/angular/angular/blob/5d3bc743d254092dd423dfb8790a7bb150deb03a/packages/core/rxjs-interop/src/to_signal.ts#L128) - The adapter function converting an Observable stream into a synchronous or undefined-initialized signal.
- [Angular Resource API Declarations](https://github.com/angular/angular/blob/5d3bc743d254092dd423dfb8790a7bb150deb03a/packages/core/src/resource/api.ts#L79) - TypeScript definitions for ResourceStatus, ResourceRef, and stream loader parameters.
- [Angular Core Resource State Machine Source Code](https://github.com/angular/angular/blob/5d3bc743d254092dd423dfb8790a7bb150deb03a/packages/core/src/resource/resource.ts#L68) - The internal promise and stream lifecycle runner powering modern Angular resources.
- [RxJS catchError Source Code](https://github.com/ReactiveX/rxjs/blob/e5351d02e225e275ac0e497c7b66eaa5f0c88791/src/internal/operators/catchError.ts#L105) - The operator implementation for error interception and stream replacement in RxJS pipelines.
- [RxJS switchMap Source Code](https://github.com/ReactiveX/rxjs/blob/e5351d02e225e275ac0e497c7b66eaa5f0c88791/src/internal/operators/switchMap.ts#L85) - Concurrency operator source code that cancels previous active inner subscriptions on new triggers.
- [RxJS exhaustMap Source Code](https://github.com/ReactiveX/rxjs/blob/e5351d02e225e275ac0e497c7b66eaa5f0c88791/src/internal/operators/exhaustMap.ts#L68) - Concurrency operator that drops incoming triggers while an inner subscription is in flight.
- [RxJS concatMap Source Code](https://github.com/ReactiveX/rxjs/blob/e5351d02e225e275ac0e497c7b66eaa5f0c88791/src/internal/operators/concatMap.ts#L78) - Concurrency operator that sequentially queues multiple inner subscriptions without dropping or cancelling.
- [RxJS debounceTime Source Code](https://github.com/ReactiveX/rxjs/blob/e5351d02e225e275ac0e497c7b66eaa5f0c88791/src/internal/operators/debounceTime.ts#L63) - Timing operator delaying stream emissions until a specified quiet duration elapses.
- [Angular Async Reactivity with Resources Guide](https://angular.dev/guide/signals/resource) - Official architectural guide covering reactive params, loaders, and resource status transitions.
- [Angular RxJS Interop Guide](https://angular.dev/ecosystem/rxjs-interop) - Official guide on bridging RxJS Observables and Signals using toSignal and toObservable.
- [Angular ResourceStatus API Reference](https://angular.dev/api/core/ResourceStatus) - Reference documentation for resource lifecycle states including idle, loading, resolved, reloading, and local.
- [Angular ResourceRef API Reference](https://angular.dev/api/core/ResourceRef) - Reference documentation for resource control methods including reload, update, set, and hasValue.
