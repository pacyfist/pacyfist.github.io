---
tags: ["typescript", "angular", "signals", "rxresource", "error-handling"]
categories: ["typescript", "angular"]
title: "Angular rxResource: Error Handling is Not What You Think"
published: false
---

I moved a data-fetching pipeline over to `rxResource`, kept my usual `.pipe(catchError(...))` safety net, pointed it at an endpoint that returns a 500, and got nothing. No error banner. `resource.error()` was `undefined`. `resource.status()` said `'resolved'`.

That is the interesting part, so I stopped guessing and built a throwaway Angular 22.1.3 project to measure what actually happens. Every status string, error class, and log line below is taken from that project's output — a few of the longer JSON lines are wrapped for readability, but nothing is invented. Some of it contradicts what I expected, and a decent amount of it contradicts what the top search results for "rxResource error handling" will tell you.

Here is what I found.

## Zeroth trap: the code you copied does not compile

Before any error handling, the API itself. Any rxResource example written against Angular 19 looks like this:

```typescript
userResource = rxResource({
  request: () => this.userId(),
  loader: ({ request }) => this.http.get<UserProfile>(`/api/users/${request}`),
});
```

Paste that into Angular 22 and `tsc` says no:

```text
src/app/post-original.ts(22,5): error TS2769: No overload matches this call.
  Overload 1 of 2, '(opts: RxResourceOptions<unknown, unknown> & { defaultValue: unknown; }): ResourceRef<unknown>', gave the following error.
    Object literal may only specify known properties, and 'request' does not exist in type 'RxResourceOptions<unknown, unknown> & { defaultValue: unknown; }'.
  Overload 2 of 2, '(opts: RxResourceOptions<unknown, unknown>): ResourceRef<unknown>', gave the following error.
    Object literal may only specify known properties, and 'request' does not exist in type 'RxResourceOptions<unknown, unknown>'.
src/app/post-original.ts(23,16): error TS7031: Binding element 'request' implicitly has an 'any' type.
```

`request` became `params`, and for `rxResource` specifically `loader` became `stream`. I checked the shipped type definitions across four majors rather than trusting a changelog:

| Angular | rxResource options   | `error` signal type          |
| ------- | -------------------- | ---------------------------- |
| 19.2    | `request` + `loader` | `Signal<unknown>`            |
| 20.3    | `params` + `stream`  | `Signal<Error \| undefined>` |
| 21.2    | `params` + `stream`  | `Signal<Error \| undefined>` |
| 22.1    | `params` + `stream`  | `Signal<Error \| undefined>` |

The deprecated aliases are gone, not merely discouraged. The whole `RxResourceOptions` interface in Angular 22 is two lines:

```typescript
interface RxResourceOptions<T, R> extends BaseResourceOptions<T, R> {
  stream: (params: ResourceLoaderParams<R>) => Observable<T>;
}
```

The rename is not cosmetic. `loader` implied one value; `stream` means Angular consumes _every_ emission. That matters later.

## The mental model: ResourceStatus

```typescript
type ResourceStatus =
  | "idle"
  | "error"
  | "loading"
  | "reloading"
  | "resolved"
  | "local";
```

That union is accurate in Angular 22. The distinction that actually bites is **`loading` vs `reloading`**, and I measured both against a real HTTP server:

```text
[REAL] real-reload-vs-load :: {
  "resolved":     {"status":"resolved",  "value":{"id":"usr_123","name":"Ada Lovelace","role":"Engineer"}},
  "duringReload": {"status":"reloading", "value":{"id":"usr_123","name":"Ada Lovelace","role":"Engineer"}},
  "duringLoad":   {"status":"loading"},
  "after404":     {"status":"error","httpStatus":404}
}
```

- Change the `params` signal → `'loading'`, and `value()` drops to `undefined`. The card on screen goes blank.
- Call `reload()` → `'reloading'`, and `value()` keeps the previous value. The card stays on screen.

If your list flickers empty on every refresh, you changed `params` when you wanted `reload()`.

## Trap 1: catchError with a fallback value

Here is the code that started this, ported to the Angular 22 API:

```typescript
swallowed = rxResource({
  stream: () =>
    this.http.get<UserProfile>("/api/boom").pipe(
      catchError(() => of(null)), // the trap
    ),
});
```

Against a server that really returns `500 {"message":"Database is on fire"}`:

```text
[REAL] real-of-null :: {"status":"resolved","value":null}
```

And from the mocked-backend run, with a couple of extra fields:

```text
[PROBE] catchError-of-null :: {"status":"resolved","value":null,"isLoading":false,"hasValue":true}
```

`catchError(() => of(null))` does exactly what RxJS promises: it swallows the error and emits `null` as a perfectly ordinary next value, then completes. From the resource's side nothing went wrong, so the status is `'resolved'`, `error()` is `undefined`, and your `@case ('error')` branch never runs.

Note `hasValue: true`. `null` is a value. `hasValue()` is not a null check, and the empty card renders happily.

## Trap 2: catchError with EMPTY

The obvious next idea is to emit nothing at all:

```typescript
emptied = rxResource({
  stream: () =>
    this.http.get<UserProfile>("/api/boom").pipe(catchError(() => EMPTY)),
});
```

I had assumed this hangs in `'loading'` forever. It does not — Angular 22 handles it explicitly:

```text
[REAL] real-EMPTY :: {"status":"error","errCtor":"RuntimeError","errMessage":"NG0991: Resource completed before producing a value"}
```

You get an error state, but the error is Angular's `RuntimeError` NG0991, not your server's `HttpErrorResponse`. The status code, the response body, the URL — all gone. You traded a silent success for a useless failure. It is in the framework source as a plain branch on the subscription:

```typescript
complete: () => {
  if (!hasResolved) {
    send({
      error: new RuntimeError(
        991,
        "Resource completed before producing a value",
      ),
    });
  }
};
```

## The rule for rxResource streams

If you want the resource to manage error state, **the error has to escape the stream**:

```typescript
bubbled = rxResource({
  params: () => this.userId(),
  stream: ({ params }) => this.http.get<UserProfile>(`/api/users/${params}`),
});
```

```text
[REAL] real-bubble :: {
  "status":"error",
  "isHttpErrorResponse":true,
  "isErrorInstance":false,
  "httpStatus":500,
  "statusText":"Internal Server Error",
  "body":{"message":"Database is on fire"},
  "message":"Http failure response for http://localhost:4300/api/boom: 500 Internal Server Error"
}
```

Status code, status text and the parsed response body all survive. For logging or side effects, use `tap` — it observes the error without consuming it. I verified both halves of that claim:

```typescript
stream: ({ params }) =>
  this.http
    .get<UserProfile>(`/api/users/${params}`)
    .pipe(
      tap({ error: (err) => this.logger.error("Failed fetching user", err) }),
    );
```

```text
[PROBE] tap-error :: {"logged":1,"status":"error","httpStatus":503}
```

Logged once, still an error, still carrying 503.

## Trap 3: the type of error() is a moving target

Every older article says `error` is `Signal<unknown>`. It was, in 19.2. Since v20 it is:

```typescript
readonly error: Signal<Error | undefined>;
```

Which sets up a genuinely strange result. Look again at the probe above:

```text
"isHttpErrorResponse": true,
"isErrorInstance": false
```

`HttpErrorResponse` is not an `Error`. It is declared as

```typescript
declare class HttpErrorResponse extends HttpResponseBase implements Error {
  readonly name = 'HttpErrorResponse';
  readonly message: string;
  ...
}
```

It _implements_ `Error` structurally but extends `HttpResponseBase`, so `instanceof Error` is `false` — yet Angular hands it to you through a signal typed `Error`. That works because of a duck-typing check in the resource internals:

```typescript
function isErrorLike(error) {
  return (
    error instanceof Error ||
    (typeof error === "object" &&
      typeof error.name === "string" &&
      typeof error.message === "string")
  );
}

function encapsulateResourceError(error) {
  if (isErrorLike(error)) return error;
  return new ResourceWrappedError(error);
}
```

`HttpErrorResponse` has a string `name` and a string `message`, so it passes and reaches you intact.

**This is the part worth knowing if you are on an older version.** In Angular 20 that same function reads:

```typescript
function encapsulateResourceError(error) {
  if (error instanceof Error) return error;
  return new ResourceWrappedError(error);
}
```

No duck typing. On Angular 20 and 21.0, every `HttpErrorResponse` got wrapped, and you had to dig it out of `.cause`. This is the message people were reporting:

```text
Resource returned an error that's not an Error instance: [object Object].
Check this error's .cause for the actual error.
```

I read that older behaviour out of the published `@angular/core@20.3.29` bundle rather than running it, and `isErrorLike` first appears in `21.1.0` — `21.0.3` does not have it. So: on 20.x and 21.0 you need `.cause`; from 21.1 onwards that advice is wrong, because `.cause` is `undefined` and the status sits directly on `error()`.

Non-`Error` throws are still wrapped, which I confirmed:

```text
[PROBE] non-error-throw :: {
  "status":"error",
  "ctor":"ResourceWrappedError",
  "message":"Resource returned an error that's not an Error instance: just a string. Check this error's .cause for the actual error.",
  "cause":"just a string"
}
```

So the narrowing helper is still the right pattern, just for a different reason — you are narrowing from `Error`, not from `unknown`:

```typescript
readonly httpError = computed(() => {
  const err = this.bubbled.error();
  return err instanceof HttpErrorResponse ? err : null;
});
```

TypeScript accepts that narrowing and the template type-checks:

{% raw %}

```html
@if (httpError(); as err) {
<div class="alert alert-error">
  Error {{ err.status }}: {{ err.error?.message || err.statusText }}
</div>
}
```

{% endraw %}

```text
[PROBE] computed-narrowing :: {"narrowed":true,"status":404,"statusText":"Not Found","bodyMessage":"nope"}
```

## Trap 4: value() throws in the error state

The API docs for `ResourceStatus` say that in the `error` state "`value()` will be `undefined`". That is not what happens:

```text
[PROBE] value-in-error-state :: {
  "threw":true,
  "ctor":"ResourceValueError",
  "message":"Resource is currently in an error state (see Error.cause for details): Http failure response for /api/users/usr_123: 500 x",
  "causeCtor":"HttpErrorResponse"
}
```

It throws `ResourceValueError`, with the real error on `.cause`. The `Resource.value` API reference is the accurate one: "The current value of the `Resource`, or throws an error if the resource is in an error state."

`ResourceValueError` is not exported from `@angular/core`, so you cannot catch it by type. Guard with `hasValue()` instead, which is a proper type guard:

{% raw %}

```html
@if (userResource.hasValue()) {
<h2>{{ userResource.value().name }}</h2>
}
```

{% endraw %}

Note there is no `?.` there — inside the guard, `value()` is narrowed to non-undefined.

## Cancellation actually works

This one I expected to be oversold, and it wasn't. Changing `params` tears down the in-flight request. Not "unsubscribes locally" — the socket really closes. My throwaway API server logs client aborts, and I typed three characters into a 3-second endpoint:

```text
2026-08-26T13:50:18.709Z GET /api/slow?q=a
  !! ABORTED BY CLIENT: /api/slow?q=a
2026-08-26T13:50:19.114Z GET /api/slow?q=ab
  !! ABORTED BY CLIENT: /api/slow?q=ab
2026-08-26T13:50:19.524Z GET /api/slow?q=abc
```

Only the last one survived, and the whole test finished in 3871 ms rather than 9 s. No `switchMap`.

The stream callback also receives an `abortSignal`, already wired to the same lifecycle. `HttpClient` does not need it. A raw `fetch` does:

```typescript
search = rxResource({
  params: () => this.query(),
  stream: ({ params, abortSignal }) =>
    from(
      fetch(`/api/slow?q=${params}`, { signal: abortSignal }).then((r) =>
        r.json(),
      ),
    ),
});
```

```text
2026-08-26T13:50:22.665Z GET /api/slow?q=a
  !! ABORTED BY CLIENT: /api/slow?q=a
2026-08-26T13:50:23.073Z GET /api/slow?q=ab
```

Aborted on the wire, same as `HttpClient`. Drop the `signal` option and run the identical test, and the server sees no abort at all:

```text
2026-08-26T13:55:17.032Z GET /api/slow?q=a
2026-08-26T13:55:17.440Z GET /api/slow?q=ab
```

Both requests run to completion. The resource still shows the right answer — `{"status":"resolved","value":{"q":"ab"}}` — so nothing looks broken from inside the component, which is exactly what makes it easy to ship. The superseded request just keeps burning a connection and server time until it finishes, and its response is thrown away.

## The bit nobody mentions: it is a stream

Because the option is called `stream` and not `loader`, `rxResource` keeps consuming after the first emission. I pushed three things through a `Subject`:

```text
[PROBE] multi-emit :: {
  "before": {"status":"loading",  "value":-1},
  "first":  {"status":"resolved", "value":10},
  "second": {"status":"resolved", "value":20},
  "afterErr": {"status":"error","value":"THREW:ResourceValueError","error":"late failure"}
}
```

Every emission updates `value()` while the status stays `'resolved'` — no reload, no `params` change. And an error arriving _after_ a successful value still flips the resource into `'error'` and makes `value()` throw. If you back an `rxResource` with a WebSocket or a polling stream, a late failure will blow away a value that was rendering fine a moment ago.

`defaultValue: -1` is also visible during `'loading'`, which is a tidier way to avoid `undefined` than sprinkling `?.` everywhere.

## Recovery

Worth knowing that the error state is not sticky. Changing `params` after a failure resolves normally, and `error()` goes back to `undefined` (which is why it vanishes from the serialised log line below):

```text
[PROBE] recovery :: {
  "errored":{"status":"error","hasValue":false},
  "duringRecovery":{"status":"loading"},
  "final":{"status":"resolved","value":{"id":"good","name":"G","role":"r"}}
}
```

`reload()` after an error goes to `'reloading'`, not `'loading'`, even though there is no previous value to preserve:

```text
[PROBE] reload-after-error :: {"reloadReturn":true,"status":"reloading"}
[PROBE] reload-after-error-final :: {"status":"resolved","value":{"id":"x","name":"X","role":"r"}}
```

So a spinner keyed on `status() === 'loading'` will not appear when the user hits your retry button. Key it on `isLoading()`, which covers both.

## So should I use toSignal or rxResource?

This is the question I actually get asked, and "rxResource is the new one" is not an answer. Both live in `@angular/core/rxjs-interop`, both turn an `Observable` into a signal, both unsubscribe when their injection context is destroyed. So I ran them side by side on the same endpoints — eleven more probes — and the differences are sharper than I expected.

### What they have in common

- Same package, same auto-cleanup. Neither leaks a subscription when the component dies.
- **Both keep consuming the whole stream.** `toSignal` is not "first value only" and neither is `rxResource`:

  ```text
  [VS] multi-emit :: {
    "first":         {"toSignal":1,"rxResource":1,"status":"resolved"},
    "second":        {"toSignal":2,"rxResource":2,"status":"resolved"},
    "afterComplete": {"toSignal":2,"rxResource":2,"status":"resolved"}
  }
  ```

  Both also hold the last value after the source completes.

- **Both are effect-scheduled, not synchronous.** I assumed `rxResource` would call `params()` eagerly at construction. It does not:

  ```text
  [VS] toObservable-timing      :: {"syncAfterCreate":[],"afterFirstTick":[1],"syncAfterSet":[1],"afterTick":[1,2]}
  [VS] rxResource-params-timing :: {"afterCreate":[],"afterTick":[1]}
  ```

  Nothing happens until change detection runs, for either one.

### Where they genuinely differ

The headline difference is that **`toSignal` models a value and `rxResource` models a request**. Everything below falls out of that.

**1. Errors.** `toSignal` re-throws on read. There is no non-throwing way to ask "did this fail?":

```text
[VS] error-behaviour :: {
  "toSignal":  {"ok":false,"threw":"HttpErrorResponse","message":"Http failure response for /api/users/x: 500 Server Error"},
  "rxResource":{
    "status":"error",
    "errorCtor":"HttpErrorResponse",
    "httpStatus":500,
    "readValue":{"ok":false,"threw":"ResourceValueError","message":"Resource is currently in an error state (see Error.cause for details): Http failure response for /api/users/y: 500 Server Error"}
  }
}
```

Both throw if you read the value. Only `rxResource` also gives you `status()`, `error()` and `hasValue()` to check _first_. With `toSignal` your template has no safe question to ask.

**2. Recovery — this is the big one.** An RxJS error terminates the stream. If you build reactive params the classic way, `toObservable(id).pipe(switchMap(fetch))`, one failed request kills the pipeline permanently. Changing the input signal afterwards fetches _nothing_:

```text
[VS] recovery :: {
  "toSignal":  {"refetched":0,"read":{"ok":false,"threw":"HttpErrorResponse","message":"Http failure response for /api/u/bad: 500 e"}},
  "rxResource":{"refetched":1,"status":"resolved","read":{"ok":true,"value":{"id":"good","name":"G","role":"r"}}}
}
```

`refetched: 0`. The user picks a different record and the screen stays stuck on the old error, forever, with no network activity. I have shipped this bug. `rxResource` treats each `params` value as a fresh request, so it just recovers.

**3. Loading state.** `toSignal` has one slot, so `undefined` means both "still waiting" and "loaded nothing":

```text
[VS] before-response :: {"toSignalCanTellLoadingApartFromEmpty":false,"rxResource":{"status":"loading","isLoading":true,"hasValue":false}}
```

The `toSignal` reading is missing from that line because it was `undefined`, and `JSON.stringify` drops undefined keys — which is the point.

**4. Stale vs blank during a refetch.** Neither is universally better, but you should pick deliberately. With `switchMap`, the old value stays on screen until the new one lands. `rxResource` blanks it:

```text
[VS] during-second-load :: {"toSignal":{"id":"a","name":"Ada","role":"dev"},"rxResourceStatus":"loading","rxResourceIsLoading":true}
[VS] previous-cancelled  :: {"toSignalOpen":0,"rxResourceOpen":0}
```

Again `rxResourceValue` is absent from the log because it is `undefined`, while `toSignal` still holds Ada. Both cancelled the superseded request — `switchMap` is not worse here, just different about what it shows meanwhile. If you want `rxResource` to keep the old value, that is what `reload()` is for.

**5. `toSignal` can be synchronous; `rxResource` cannot.** With a `BehaviorSubject` and `requireSync: true`, the value is there before the first tick:

```text
[VS] sync-initial-value :: {
  "beforeTick":{"toSignal":42,"rxResource":{"status":"loading","value":-1}},
  "after":     {"toSignal":42,"rxResource":{"status":"resolved","value":42}}
}
```

If you are adapting a store, a `BehaviorSubject`, or router state that always has a current value, `toSignal(..., { requireSync: true })` gives you `Signal<T>` with no `undefined` in the type. `rxResource` will always pass through `'loading'` first, and `defaultValue` only papers over it.

**6. `rxResource` is a small state machine; `toSignal` is a cast.** The resource is writable and re-runnable:

```text
[VS] writable :: {
  "before":{"status":"resolved","value":1},
  "afterSet":{"status":"local","value":99},
  "reloadReturn":true,
  "afterReload":{"status":"resolved","value":1},
  "toSignalHasSet":"undefined",
  "rxResourceApi":["set","update","reload","destroy","hasValue","snapshot","asReadonly"]
}
```

Note the `'local'` status after `set()` — that is what the sixth member of `ResourceStatus` is for: optimistic updates. `reload()` then throws the local edit away and refetches. `toSignal` has none of this, and no `.set`.

**7. A bare `toSignal` has no reactive inputs at all.** This is the trap people hit when they translate a resource back to `toSignal`:

```text
[VS] bare-toSignal :: {"requestsMade":["/api/u/a"],"note":"changing the signal does not refetch at all","read":{"ok":true}}
```

The URL is read once, when the observable is constructed. You need `toObservable` + `switchMap` to get reactivity, which is where point 2 bites.

### Can you get resource behaviour out of toSignal? Yes, and that's the argument

To be fair to `toSignal`, all of this is reachable. You just have to build the state machine yourself — discriminated union, `catchError` mapping into an error branch instead of swallowing, `startWith` for the loading state:

```typescript
type State =
  | { kind: "loading" }
  | { kind: "value"; value: UserProfile }
  | { kind: "error"; error: HttpErrorResponse };

state = toSignal(
  toObservable(this.id).pipe(
    switchMap((v) =>
      this.http.get<UserProfile>(`/api/u/${v}`).pipe(
        map((value): State => ({ kind: "value", value })),
        catchError((error: HttpErrorResponse) =>
          of<State>({ kind: "error", error }),
        ),
        startWith<State>({ kind: "loading" }),
      ),
    ),
  ),
  { initialValue: { kind: "loading" } as State },
);
```

That works, and it recovers properly:

```text
[VS] hand-rolled-toSignal-state-machine :: {
  "errored":{"kind":"error","httpStatus":500},
  "duringSecond":"loading",
  "refetched":1,
  "final":{"kind":"value","value":{"id":"good","name":"G","role":"r"}}
}
```

Two things worth noticing. The `catchError` is _inside_ the `switchMap`, so it only terminates the inner request — that is what keeps the outer stream alive and is the whole difference from probe 2. And it uses `catchError(() => of(...))`, the exact operator this post opened by calling a trap. It is fine here precisely because the fallback is a tagged `error` state rather than a fake success. The trap was never `catchError`; it was throwing away the distinction.

Fifteen lines to hand-roll what `rxResource` does in four, and you have to get the operator placement right. That is the argument for `rxResource`, and it is a better argument than "it's newer".

### My rule

- **`rxResource`** when you are _fetching_ something: an HTTP call, anything with reactive parameters, anything that can fail and be retried, anything that needs a spinner. That is most data loading.
- **`toSignal`** when you are _adapting_ something that already exists and does not fail: a `BehaviorSubject` in a service, router params, a third-party library's observable, a WebSocket feed you have already made error-proof. Reach for `requireSync: true` whenever the source guarantees a value.
- If you find yourself writing a `{ loading, value, error }` union around a `toSignal`, stop — you are reimplementing `rxResource`.

One practical note on versions. In Angular 21's `rxjs-interop.d.ts` there are exactly three `@experimental` tags, and all three are `rxResource` — the two overloads and `RxResourceOptions`. `toSignal` and `toObservable` carry none; the interop types around them are tagged `@publicApi 20.0`. In Angular 22 those same three lines read `@publicApi 22.0`.

So `rxResource` graduated in Angular 22, and the `request`/`loader` churn from the top of this post is exactly what the experimental label was warning about. If you are on 21 or earlier it is still the better tool for fetching — just know which of the two you are betting on.

## Summary checklist

1. **Use `params` and `stream`.** `request` and `loader` no longer exist — any example written against Angular 19 will not compile.
2. **Never `catchError(() => of(fallback))`** unless you genuinely want that fallback treated as a successful `'resolved'`. `hasValue()` will be `true` even for `null`.
3. **Never `catchError(() => EMPTY)`.** You get NG0991 instead of your server's error, which is strictly worse than both alternatives.
4. **Let errors bubble.** Use `tap({ error })` for logging — it does not consume the error.
5. **`error()` is `Signal<Error | undefined>`**, not `unknown`. `HttpErrorResponse` arrives unwrapped on Angular 21.1+; on 20.x and 21.0 look in `.cause`.
6. **Guard with `hasValue()`, never assume `value()` returns `undefined` on error** — it throws `ResourceValueError`.
7. **`reload()` preserves the current value; changing `params` clears it.** Use `isLoading()` for spinners so retries are covered.
8. **Remember it is a stream.** Late emissions overwrite `value()`; a late error discards it.
9. **Use `rxResource` to fetch, `toSignal` to adapt.** A `toSignal` fed by `toObservable` + `switchMap` dies permanently on the first error unless you `catchError` _inside_ the `switchMap`.

## How I got these logs

Every `[PROBE]`, `[REAL]` and `[VS]` line above came out of a test run, so here is the whole harness. It is small enough to retype, and the fiddly parts are not obvious.

Start with a stock project:

```bash
npx @angular/cli@latest new rxres-demo --style=css --ssr=false --zoneless --defaults
cd rxres-demo
```

That gave me Angular 22.1.3, TypeScript 6.0.3, RxJS 7.8.2, and a Vitest runner already wired up. No extra dependencies are needed for anything in this post.

### The probe pattern

A "probe" is just a `console.log` with a prefix I can grep for. Put this at the top of the spec file:

```typescript
function log(label: string, obj: unknown) {
  console.log("[PROBE] " + label + " :: " + JSON.stringify(obj));
}
```

The prefix matters more than it looks — a test run prints a lot of noise, and `grep '\[PROBE\]'` is how you get a clean table of results at the end.

`JSON.stringify` is deliberate rather than lazy. It renders a whole snapshot on one line, and it **drops keys whose value is `undefined`**, which is why a few log lines above are missing a field. When `toSignal` has not emitted yet, the key just is not there. That absence is the measurement.

### Gotcha: `ng test` hides your console output

This cost me a while. The obvious command prints nothing:

```bash
ng test --no-watch          # 0 probe lines
ng test --no-watch --reporters=default   # 13 probe lines
```

Vitest's default non-interactive reporter intercepts `stdout` from tests. Passing `--reporters=default` explicitly restores it. So the command you actually want is:

```bash
ng test --no-watch --reporters=default 2>&1 | grep '\[PROBE\]'
```

### Gotcha: one `TestBed.tick()` is not enough

This is the real trick, and it is why you cannot just assert straight after flushing a response.

A resource settles through two different mechanisms. Internally it resolves a promise, so you need to let the microtask queue drain. Externally its signals only recompute when change detection runs, and the project is zoneless, so nothing runs on its own. You need both, interleaved:

```typescript
async function settle() {
  for (let i = 0; i < 5; i++) {
    await Promise.resolve();
    TestBed.tick();
  }
}
```

Five rounds is insurance, not a measurement. I checked how many are actually required for a plain HTTP resource:

```text
[H] settle-rounds :: {
  "after flush, 0 rounds":"loading",
  "after 1 round(s)":"resolved",
  "after 2 round(s)":"resolved", ...
}
```

One round was enough here; zero is not. The count depends on how many promise hops your stream involves, so a small loop beats a magic number. Skip it entirely and you will "discover" that `rxResource` never leaves `'loading'`, and write a blog post about it.

The flip side is that this also lets you observe intermediate states on purpose. To catch the `'loading'` vs `'reloading'` difference, read the signals after a single `TestBed.tick()` and _before_ flushing the response:

```typescript
userId.set("b");
TestBed.tick();
const afterParamsChange = { status: res.status(), value: res.value() }; // 'loading'
ctrl.expectOne("/api/users/b").flush({ id: "b", name: "Bob", role: "ops" });
await settle();
```

### Gotcha: `value()` throws, so you cannot just log it

Since `value()` throws in the error state, a probe that reads it will fail the test instead of reporting. Wrap it:

```typescript
function tryRead(fn: () => unknown): unknown {
  try {
    return { ok: true, value: fn() };
  } catch (e: any) {
    return { ok: false, threw: e?.constructor?.name, message: e?.message };
  }
}
```

That is where `{"ok":false,"threw":"ResourceValueError", ...}` in the logs comes from.

Log `e.constructor.name`, not `e.name`. Angular's two wrapper classes are indistinguishable by `name`:

```text
[H] error-names :: {
  "wrapped":   {"ctor":"ResourceWrappedError","name":"Error"},
  "valueError":{"ctor":"ResourceValueError","name":"Error"}
}
```

### Spec 1: deterministic transitions with HttpTestingController

For anything about status ordering, a fake backend is better than a real one, because you decide exactly when the response lands:

```typescript
describe("rxResource error handling", () => {
  let http: HttpClient;
  let ctrl: HttpTestingController;
  let injector: Injector;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpClient);
    ctrl = TestBed.inject(HttpTestingController);
    injector = TestBed.inject(Injector);
  });

  it("catchError(() => of(null)) yields resolved/null/no-error", async () => {
    const res = rxResource({
      params: () => "usr_123",
      stream: ({ params }) =>
        http
          .get<UserProfile>("/api/users/" + params)
          .pipe(catchError(() => of(null as any))),
      injector,
    });

    TestBed.tick();
    ctrl
      .expectOne("/api/users/usr_123")
      .flush({ message: "boom" }, { status: 500, statusText: "Server Error" });
    await settle();

    log("catchError-of-null", {
      status: res.status(),
      value: res.value(),
      error: res.error(),
      hasValue: res.hasValue(),
    });
    expect(res.status()).toBe("resolved");
  });
});
```

Two details that are easy to miss.

First, that `injector` property is not optional decoration. `rxResource` needs an injection context, and without one you get:

```text
[H] no-injector :: {"threw":"RuntimeError","message":"NG0203: rxResource() can only be used within an injection context such as a constructor, a factory function, a field ini..."}
```

Passing `injector` explicitly is what lets you create resources directly in a test instead of wrapping every case in a host component.

Second, `ctrl.expectOne(...)` finds nothing until you tick, because the `params` function is effect-scheduled:

```text
[H] params-effect-scheduled :: {"openRequestsBeforeTick":0,"afterTick":1}
```

`HttpTestingController` also answers the cancellation question without any network at all: `expectOne()` returns a `TestRequest` with a `.cancelled` flag, and `ctrl.match(...)` returns everything still open.

### Spec 2: a real server, for the things mocks cannot prove

`HttpTestingController` can tell you Angular unsubscribed. It cannot tell you a socket closed. For that I wrote a throwaway server — this is the entire thing, saved as `api-server.mjs` in the project root:

```javascript
import { createServer } from "node:http";

const users = {
  usr_123: { id: "usr_123", name: "Ada Lovelace", role: "Engineer" },
};

createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  res.setHeader("Access-Control-Allow-Origin", "*");
  console.log(`${new Date().toISOString()} ${req.method} ${req.url}`);
  req.on("aborted", () => console.log(`  !! ABORTED BY CLIENT: ${req.url}`));

  if (url.pathname === "/api/boom") {
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ message: "Database is on fire" }));
    return;
  }
  if (url.pathname === "/api/slow") {
    const t = setTimeout(() => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ q: url.searchParams.get("q"), at: Date.now() }));
    }, 3000);
    req.on("aborted", () => clearTimeout(t));
    return;
  }
  const m = url.pathname.match(/^\/api\/users\/(.+)$/);
  if (m) {
    const u = users[m[1]];
    if (!u) {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ message: "no such user" }));
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify(u));
    return;
  }
  res.writeHead(404);
  res.end();
}).listen(4300, () => console.log("api on 4300"));
```

`req.on('aborted', ...)` is the whole point. That handler is the only reason I can claim cancellation reaches the wire rather than just stopping at the RxJS boundary.

The matching spec swaps the fake backend for the fetch backend and talks to `localhost:4300`:

```typescript
beforeEach(() => {
  TestBed.configureTestingModule({
    providers: [provideHttpClient(withFetch())],
  });
  http = TestBed.inject(HttpClient);
  injector = TestBed.inject(Injector);
});
```

Real responses arrive whenever they arrive, so `settle()` is not enough — you need to poll, still ticking as you go:

```typescript
async function waitFor(pred: () => boolean, ms = 8000) {
  const start = Date.now();
  while (!pred()) {
    if (Date.now() - start > ms)
      throw new Error("timeout waiting for condition");
    await new Promise((r) => setTimeout(r, 25));
    TestBed.tick();
  }
  TestBed.tick();
}
```

Then `await waitFor(() => !res.isLoading())` before each probe. Remember to raise the per-test timeout when you are hitting a deliberately slow endpoint — the abort test takes about four seconds, so it is declared as `it('...', async () => { ... }, 20000)`.

Run it in two terminals:

```bash
node api-server.mjs                                    # terminal 1
ng test --no-watch --reporters=default 2>&1 | grep '\[REAL\]'   # terminal 2
```

The abort lines show up in terminal 1, not in the test output. That is the log quoted in the cancellation section.

### The type-level claims

Nothing above proves that the old `request`/`loader` code fails to compile — tests only run code that already compiled. For that, write the broken version into a plain `.ts` file in `src/app/` and ask the compiler directly:

```bash
npx tsc -p tsconfig.app.json --noEmit
```

That is where the `TS2769` block at the top of this post comes from. The template type-checking claims needed a full `ng build`, since `tsc` alone does not check Angular templates.

For the cross-version table I did not read release notes. I installed each version into a scratch folder and read what actually shipped:

```bash
npm i @angular/core@19.2   # then @20, @21, @22
grep -rn "interface RxResourceOptions" -A 4 node_modules/@angular/core/types/rxjs-interop.d.ts
grep -rn "readonly error: Signal" node_modules/@angular/core/types/_api-chunk.d.ts
grep -n "function encapsulateResourceError" -A 8 node_modules/@angular/core/fesm2022/_resource-chunk.mjs
```

The `.d.ts` files answer "what does the API look like", the `fesm2022` bundles answer "what does it actually do". Both ship inside the npm package, so this works for any version you can install, including ones you are not running. Older layouts differ slightly — before v22 the type files live at `node_modules/@angular/core/index.d.ts` and `rxjs-interop/index.d.ts` — so `grep -rn` across the package beats guessing the path.

### Scoreboard

35 tests, all green, across four spec files: deterministic transitions, the real server, `toSignal` versus `rxResource` side by side, and a fourth one that only exists to check the claims in this section.

The two results I would have gotten wrong by reasoning alone are the `EMPTY` behaviour and the `instanceof Error` check — both came out the opposite of my guess. That is the argument for measuring rather than reasoning, and it applies to the harness too: I wrote "two rounds is usually enough" in a draft of this section, then measured and found one was.

## Sources

- [Angular: Async reactivity with resources](https://angular.dev/guide/signals/resource)
- [Angular API: `rxResource`](https://angular.dev/api/core/rxjs-interop/rxResource)
- [Angular API: `RxResourceOptions`](https://angular.dev/api/core/rxjs-interop/RxResourceOptions)
- [Angular API: `Resource`](https://angular.dev/api/core/Resource) — the `error: Signal<Error | undefined>` declaration
- [Angular API: `HttpErrorResponse`](https://angular.dev/api/common/http/HttpErrorResponse)
- [`packages/core/src/resource/resource.ts`](https://github.com/angular/angular/blob/main/packages/core/src/resource/resource.ts) — `isErrorLike`, `encapsulateResourceError`, `ResourceValueError`, `ResourceWrappedError`
- [The same file at tag 20.0.0](https://github.com/angular/angular/blob/20.0.0/packages/core/src/resource/resource.ts) — the `instanceof Error` version
- [angular/angular#61861 — resource does not recognize HttpErrorResponse as error](https://github.com/angular/angular/issues/61861)
- [angular/angular#62111 — refactor(core): Support Error like object for resource errors](https://github.com/angular/angular/pull/62111) — the fix that stopped the wrapping
- [angular/angular discussion #60121 — Resource RFC 2: APIs](https://github.com/angular/angular/discussions/60121) — background on the `loader` → `stream` rename
- [Angular: RxJS interop](https://angular.dev/ecosystem/rxjs-interop) — `toSignal`, `toObservable`, `initialValue`, `requireSync`, `manualCleanup`
- [Angular API: `toSignal`](https://angular.dev/api/core/rxjs-interop/toSignal) — the signal "will throw an error if the `Observable` errors"
