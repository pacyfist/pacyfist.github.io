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

I built the same user lookup both ways, then tested parameter changes, gating, loading, errors, recovery, fallback values, reloads, concurrency, debouncing, mutations, and cleanup.

Here is what happened in each real-world scenario.

## The lab

I created a throwaway Angular workspace for these experiments:

```bash
npx --yes @angular/cli@22.2.0 new rxresource-lab \
  --style=css --ssr=false --zoneless --defaults --skip-git
```

The CLI created the project and installed its packages successfully:

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

I ran the whole test suite in one process:

```bash
npx ng test --watch=false --reporters=verbose
```

```text
Test Files  1 passed (1)
     Tests  12 passed (12)
  Duration  1.61s
```

The log lines in each chapter below came from that run.

## Two ways to ask for data

Before looking at the tests, here is the basic difference in mental models.

`toSignal` is a bridge:

```typescript
const user = toSignal(http.get<User>('/api/users/1'));
```

It takes an Observable that already exists, subscribes immediately, and exposes its latest emission as a signal.

`rxResource` is an entire request state machine:

```typescript
const user = rxResource({
  params: () => id(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
});
```

It tracks the lookup parameter, manages loading and error status, handles manual reloads, and cancels in-flight work when parameters change.

Comparing bare `toSignal` to `rxResource` is unfair. To get the same features out of `toSignal`, you have to write a full RxJS state pipeline. The experiments below compare both approaches side by side.

## Chapter 1: Changing parameters (The ID switch)

**The scenario:** A user browses a list and clicks from user `a` to user `b`. If request `a` is still pending, we want to cancel it immediately and start request `b`.

### The toSignal way

A common junior trap is writing this:

```typescript
const id = signal('a');
const user = toSignal(http.get<User>(`/api/users/${id()}`));

id.set('b'); // Does nothing! id() was only read once at startup.
```

`toSignal` does not track signals read inside the Observable factory. To make it reactive, you must pipe the ID signal into RxJS:

```typescript
const id = signal('a');

const user = toSignal(
  toObservable(id).pipe(
    switchMap((value) => http.get<User>(`/api/users/${value}`)),
  ),
);
```

### The rxResource way

With `rxResource`, reactive parameters are built into the API:

```typescript
const id = signal('a');

const user = rxResource({
  params: () => id(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
});
```

### What the test showed

Both reactive versions started with ID `a`, switched to `b` before `a` completed, and resolved:

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

The bare `toSignal` only subscribed once and stayed on `a`. Both reactive versions cancelled `a` cleanly and delivered `b`.

**Takeaway: `toSignal` does not manage reactivity for you.** You must explicitly bridge signals with `toObservable` and `switchMap`. `rxResource` includes reactive parameter tracking by default.

## Chapter 2: Request gating (Pausing with undefined)

**The scenario:** A profile modal opens without an active selection. We want zero HTTP requests to fire until the user picks an account. If the user deselects, we want to pause again.

### The toSignal way

In RxJS, developers typically add a `filter` operator:

```typescript
const selectedId = signal<string | undefined>(undefined);

const user = toSignal(
  toObservable(selectedId).pipe(
    filter((id): id is string => id !== undefined),
    switchMap((id) => http.get<User>(`/api/users/${id}`)),
  ),
);
```

This prevents the initial request. But there is a nasty catch: when `selectedId` resets back to `undefined`, `filter` simply drops the event. The signal stays frozen on the old user's stale data.

### The rxResource way

`rxResource` has a built-in concept of an idle state:

```typescript
const selectedId = signal<string | undefined>(undefined);

const user = rxResource({
  params: () => selectedId(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
});
```

When `params` returns `undefined`, the resource enters the `'idle'` status. It does not call `stream`, and `isLoading()` stays `false`.

When `selectedId` receives `'42'`, it transitions to `'loading'` and fetches the data. When `selectedId` clears back to `undefined`, it cancels in-flight work and returns cleanly to `'idle'`.

### What the test showed

```text
[EXP] request-gating :: {
  "gatedInitial":{"status":"idle","isLoading":false,"hasValue":false,"requestsDispatched":0},
  "afterIdSelected":{"status":"resolved","isLoading":false,"requestsDispatched":1},
  "afterIdCleared":{"status":"idle","isLoading":false,"requestsDispatched":1}
}
```

**Takeaway: Returning `undefined` from `params` pauses `rxResource` in `'idle'`.** In `toSignal`, filtering out `undefined` leaves your UI frozen with old data unless you write custom branching.

## Chapter 3: Loading states and multiple emissions

**The scenario:** You need to show a spinner before data arrives. You also want to support streams that emit multiple times, like a repository that returns cached data first and fresh network data second.

### The toSignal way

```typescript
const user = toSignal(multiEmission$);
```

Before the first emission, `user()` returns `undefined`. If you do not want `undefined`, you can pass an `initialValue`.

When `multiEmission$` emits `one`, then `two`, and completes, `user()` updates to each emission in order and holds `two` after completion.

### The rxResource way

```typescript
const user = rxResource({
  stream: () => multiEmission$,
});
```

Before any emission, `user.status()` is `'loading'` and `user.isLoading()` is `true`.

When the stream emits `one`, then `two`, `user.value()` updates on each tick, and `user.status()` switches to `'resolved'`. When the stream completes, it keeps the last value.

### What the test showed

```text
[EXP] loading-stream-completion :: {
  "initial":{"resourceStatus":"loading","resourceIsLoading":true,"resourceHasValue":false},
  "first":{"toSignal":"one","resource":"one","resourceStatus":"resolved"},
  "second":{"toSignal":"two","resource":"two","resourceStatus":"resolved"},
  "afterCompletion":{"toSignal":"two","resource":"two","resourceStatus":"resolved"}
}
```

**Takeaway: `rxResource.stream` is not limited to one HTTP response.** It tracks multi-emission streams and keeps the last value on completion, while giving you dedicated `isLoading()` and `status()` signals.

## Chapter 4: Errors and recovery (The zombie stream bug)

**The scenario:** The server returns a 500 error. The user fixes their input or clicks a different row. Does the screen recover, or is it permanently broken?

### The bare toSignal trap

```typescript
const user = toSignal(
  toObservable(id).pipe(switchMap((v) => http.get<User>(`/api/users/${v}`))),
);
```

When a 500 occurs, reading `user()` throws the error. Worse: the failed HTTP call terminates the entire Observable. Changing `id` to `'good'` does nothing. The screen is dead.

### The outer catchError trap

Many developers try to fix this by adding `catchError`:

```typescript
// Do not do this: catchError outside switchMap
const user = toSignal(
  toObservable(id).pipe(
    switchMap((v) => http.get<User>(`/api/users/${v}`)),
    catchError(() => of(null)),
  ),
);
```

This prevents the crash, but `catchError` completes the outer chain after the first failure. The listener on `id` is gone. When the user picks a new ID, nothing happens.

### The correct toSignal way (Tagged Union)

To make `toSignal` survive an error, `catchError` must live *inside* `switchMap`, wrapped in a tagged union:

```typescript
type UserState =
  | { kind: 'loading' }
  | { kind: 'value'; value: User }
  | { kind: 'error'; error: HttpErrorResponse };

const user = toSignal(
  toObservable(id).pipe(
    switchMap((value) =>
      http.get<User>(`/api/users/${value}`).pipe(
        map((u): UserState => ({ kind: 'value', value: u })),
        catchError((error) => of<UserState>({ kind: 'error', error })),
        startWith<UserState>({ kind: 'loading' }),
      ),
    ),
  ),
  { initialValue: { kind: 'loading' } as UserState },
);
```

The inner request ends on error, but the outer pipeline keeps watching `id`.

### The rxResource way

`rxResource` handles this out of the box:

```typescript
const user = rxResource({
  params: () => id(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
});
```

When the request fails, `user.status()` becomes `'error'` and `user.error()` captures the error object. When `id` changes to `'good'`, `rxResource` starts a fresh request and recovers.

### What the test showed

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

Notice `newOuterCatchRequest: false`. The outer `catchError` chain never heard the new ID. Both the tagged RxJS pipeline and `rxResource` recovered completely.

**Takeaway: Placing `catchError` outside `switchMap` permanently kills your stream.** `rxResource` avoids this bug because each parameter change runs as an independent request lifecycle.

## Chapter 5: Fallback values (When 404 is not an error)

**The scenario:** You query an optional user profile. If the server returns a 404, you want to return `null` instead of treating it as a system outage.

### Catching to of(null)

```typescript
const user = rxResource<User | null, void>({
  stream: () => http.get<User>('/api/users/missing').pipe(
    catchError(() => of(null)),
  ),
});
```

When the 404 occurs, `catchError` emits `null`. The resource sees a normal emission and resolves:

```text
[EXP] fallback-null :: {
  "status":"resolved",
  "value":null,
  "hasValue":true
}
```

This is not `rxResource` ignoring an error. The stream emitted a valid value (`null`), so the resource marked itself as `resolved`.

### The EMPTY completion trap

What if you swallow the error by returning `EMPTY` instead?

```typescript
const user = rxResource<User, void>({
  stream: () => http.get<User>('/api/users/missing').pipe(
    catchError(() => EMPTY),
  ),
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

`rxResource` expects its stream to emit at least once before completing. If it completes empty, Angular throws runtime error `NG0991`, and the original HTTP error details are lost.

**Takeaway: Returning `null` marks a resource as successful.** Returning `EMPTY` throws `NG0991`. If you need to distinguish an empty result from a broken server, do not catch the error into `EMPTY`.

## Chapter 6: Reloading while busy

**The scenario:** A user clicks a "Refresh" button twice in rapid succession while on a slow connection.

### The rxResource way

`rxResource` has a built-in `.reload()` method:

```typescript
user.reload();
```

It returns a boolean indicating whether the reload actually started. If the resource is already fetching, it returns `false` and ignores the second call. It keeps existing data visible while status flips to `'reloading'`.

### The toSignal way

`toSignal` does not have a reload method. To build one, you have to create a trigger subject and coordinate concurrency:

```typescript
const reload$ = new Subject<void>();

const user = toSignal(
  reload$.pipe(
    exhaustMap(() => http.get<User>('/api/users/1')),
  ),
);
```

Using `exhaustMap` ensures that clicks sent while busy are dropped.

### What the test showed

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

In Angular 22.2.0, `reload()` while busy returned `false` and did not start a second network request. During the reload, Ada remained available on screen.

**Takeaway: `rxResource.reload()` refuses to start while already busy and keeps stale data visible.** Use `isLoading()` for spinners, which is `true` during both initial loads and reloads.

## Chapter 7: Polling and concurrency (Cancel, ignore, or queue)

**The scenario:** A dashboard polls every few seconds, or rapid events arrive before earlier requests finish. How should overlapping work be handled?

### The toSignal power: choosing your policy

With RxJS, you pick the exact operator for your business rules:

```typescript
// 1. switchMap: cancel the active request when a new trigger arrives
toObservable(trigger).pipe(switchMap(() => http.get('/api/stats')));

// 2. exhaustMap: ignore new triggers while a request is active
toObservable(trigger).pipe(exhaustMap(() => http.get('/api/stats')));

// 3. concatMap: queue new triggers and run every request sequentially
toObservable(trigger).pipe(concatMap(() => http.get('/api/stats')));
```

### The rxResource policy

`rxResource` has fixed policies:
- Changing `params` acts like `switchMap`: it cancels any in-flight request immediately.
- Calling `.reload()` acts like `exhaustMap`: it ignores calls while a request is already running.

### What the test showed

I sent three rapid triggers before any request completed:

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

- `switchMap` cancelled the first two requests. The newest trigger won.
- `exhaustMap` ignored triggers two and three. The first request won.
- `concatMap` queued all three. Every trigger got processed.

**Takeaway: Use `toSignal` when your application requires custom queuing or throttling.** `rxResource` has fixed cancellation and reload behaviors.

## Chapter 8: Debouncing search inputs

**The scenario:** A typeahead search box where the user types "a", "b", "c". You want to wait 300 ms after the user stops typing before making a network call.

### The toSignal way

In RxJS, debouncing is a simple operator in the chain:

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

### The rxResource trap

You cannot put `debounceTime` inside `rxResource.stream`:

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

Because `query()` changes on every keystroke, `params` re-evaluates immediately. `rxResource` cancels the old stream, sets `isLoading()` to `true`, and starts a new one. The resource flaps into a loading state on every single letter.

### The clean rxResource way

With `rxResource`, debouncing belongs on the signal feeding `params`:

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

Now `params` only changes when typing stops.

### What the test showed

```text
[EXP] debouncing-typeahead :: {
  "toSignalPipeline":{"keystrokes":["a","ab","abc"],"requestsDispatched":1,"finalQuery":"abc"},
  "rxResourceAntiPattern":{"loadingStateTransitions":3,"spinnerFlickerDetected":true,"requestsDispatched":1},
  "rxResourcePreDebounced":{"loadingStateTransitions":1,"spinnerFlickerDetected":false,"requestsDispatched":1,"finalQuery":"abc"}
}
```

The anti-pattern triggered three loading transitions for three keystrokes. Pre-debouncing the signal kept the resource calm until the user paused.

**Takeaway: In `toSignal`, debouncing is a stream operator. In `rxResource`, debouncing belongs on the signal producer feeding `params`.**

## Chapter 9: Optimistic local mutations

**The scenario:** A user edits their profile name. You want the UI to update immediately, send an HTTP PATCH in the background, and roll back if the server fails.

### The toSignal limitation

A signal created with `toSignal` is strictly read-only:

```typescript
const user = toSignal(http.get<User>('/api/user/1'));

// TypeScript compile error: Property 'update' does not exist on type 'Signal<User | undefined>'
user.update((prev) => ({ ...prev, name: 'Grace Hopper' }));
```

To support mutations with `toSignal`, you have to manage a local state store or merge action streams manually.

### The rxResource way

`ResourceRef.value` is a `WritableSignal`:

```typescript
function renameUser(newName: string) {
  const current = user.value();
  if (!current) return;

  // 1. Update the UI immediately
  user.value.update((u) => (u ? { ...u, name: newName } : u));

  // 2. Persist to the server
  http.patch(`/api/users/${current.id}`, { name: newName }).subscribe({
    error: () => {
      // 3. Roll back to server truth on failure
      user.reload();
    },
  });
}
```

Calling `.update()` or `.set()` on `user.value` updates the UI instantly without firing a new network call. If the PATCH fails, one call to `user.reload()` restores the true server state.

### What the test showed

```text
[EXP] optimistic-mutations :: {
  "initialStatus":"resolved",
  "initialValue":{"id":"u1","name":"Original Name"},
  "afterOptimisticUpdate":{"status":"local","hasValue":true,"isLoading":false,"value":{"id":"u1","name":"Optimistic Name"},"networkRequestsDispatched":1},
  "afterRollbackSet":{"status":"local","value":{"id":"u1","name":"Rollback Name"},"networkRequestsDispatched":1},
  "toSignalIsWritable":false
}
```

Notice that after the local mutation, `status` transitioned to `'local'` and dispatched zero extra network requests.

**Takeaway: `rxResource.value` is writable.** You can use `.set()` and `.update()` for instant optimistic updates. `toSignal` is strictly read-only.

## Chapter 10: Teardown and cleanup

**The scenario:** A user navigates away from a page while requests are in flight or while a refresh timer is running.

### What the test showed

I destroyed the Angular injection context while both APIs had active subscriptions:

```text
[EXP] teardown :: {
  "destroyRefWasPresent":true,
  "toSignalUnsubscriptions":1,
  "resourceUnsubscriptions":1
}
```

Both unsubscribed exactly once via Angular's `DestroyRef`.

### The timer ownership rule

If a timer lives inside the Observable passed to `toSignal`, tearing down the signal tears down the timer:

```typescript
const counter = toSignal(timer(0, 1000)); // automatically cleaned up on destroy
```

If your component creates an external timer to call `resource.reload()`, your component owns that cleanup:

```typescript
const intervalId = setInterval(() => user.reload(), 10000);

// You must clean this up yourself
inject(DestroyRef).onDestroy(() => clearInterval(intervalId));
```

**Takeaway: Both APIs clean up their own subscriptions automatically.** But if your code creates an external timer to trigger `.reload()`, your code must clear that timer.

## Reading a resource safely in templates

`rxResource` exposes rich state, but templates often hide two common production bugs: null crashes and invisible reloads.

Here is the fragile pattern many developers write first:

{% raw %}

```html
<!-- Fragile template -->
@if (user.hasValue()) {
  <h2>{{ user.value().name }}</h2>
} @else if (user.error(); as error) {
  <p role="alert">Could not load user: {{ error.message }}</p>
} @else if (user.isLoading()) {
  <p>Loading...</p>
}
```

{% endraw %}

This template has two bugs:

1. **The null crash:** If your stream caught a 404 and returned `null` as a fallback, `user.hasValue()` is `true`. Reading `user.value().name` will throw `TypeError: Cannot read properties of null`.
2. **The hidden reload:** When `user.reload()` runs, `hasValue()` stays `true` to keep old data visible. Because `@if (user.hasValue())` is first, the `@else if (user.isLoading())` branch will never run during a reload. The user gets no visual confirmation that data is refreshing.

Here is the safe production pattern:

{% raw %}

```html
@if (user.isLoading() && !user.hasValue()) {
  <!-- Initial load: show skeleton before any data exists -->
  <p class="skeleton" aria-busy="true">Loading user...</p>
} @else if (user.error(); as error) {
  <!-- Error state: show message with retry button -->
  <div role="alert">
    <p>Could not load user: {{ error.message }}</p>
    <button (click)="user.reload()">Retry</button>
  </div>
} @else if (user.value(); as userData) {
  <!-- Data ready: show card, with a non-destructive spinner during reloads -->
  <article [class.opacity-50]="user.isLoading()">
    <h2>
      {{ userData.name }}
      @if (user.isLoading()) {
        <span class="spinner" aria-label="Refreshing...">Refreshing...</span>
      }
    </h2>
    <button (click)="user.reload()" [disabled]="user.isLoading()">Refresh</button>
  </article>
} @else if (user.hasValue()) {
  <!-- Explicit null fallback (e.g. 404 resolved to null) -->
  <p>User not found.</p>
} @else {
  <!-- Idle state: params returned undefined -->
  <p>Please select a user.</p>
}
```

{% endraw %}

Checking `user.value(); as userData` guarantees that `userData` is non-null. Showing the spinner inside the data block lets users read existing data while a background refresh runs.

## Which one should you use?

Use `rxResource` when you are modeling a request lifecycle:

- an entity fetched by ID or query parameters;
- screens needing initial loading and background reloading states;
- requests that need an explicit error channel and a retry button;
- optional queries that pause cleanly in an `'idle'` status when parameters are `undefined`;
- optimistic UI updates and local mutations via its writable `value` signal.

Those behaviors arrive as one consistent contract without writing custom state unions.

Use `toSignal` when you already have an Observable and want its latest value as a signal:

- store selectors, router streams, and WebSockets;
- pipelines where RxJS operators like `debounceTime`, `retry`, or `filter` define the core behavior;
- strictly read-only signal projections;
- synchronous sources like `BehaviorSubject` where `requireSync: true` returns a non-nullable `Signal<T>`.

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
