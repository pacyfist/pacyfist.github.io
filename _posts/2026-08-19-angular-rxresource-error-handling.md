---
tags: ["typescript", "angular", "signals", "rxresource", "error-handling"]
categories: ["typescript", "angular"]
title: "Angular rxResource Error Handling: catchError Lies to You"
image:
  path: /assets/img/2026-08-19/main.jpg
  alt: A safety net that catches everything and reports absolutely nothing.
---

`.pipe(catchError(() => of(null)))` is what a stream looks like once you have made it safe. In an `rxResource` it is also what makes a 500 arrive as a success.

The whole thing fits in one spec file: a resource pointed at an endpoint that answers 500, that `catchError` on the end of its stream, and a probe that prints what the resource believes afterwards.

No error state. `error()` was `undefined`. `status()` said `'resolved'`.

The safety net was the thing hiding the fire.

Every probe line below came out of a throwaway Angular 22.1.3 project, and the server logs came out of a thirty-line Node server next to it. You can trust them even where they contradict the docs. And a few of them do.

Long lines are wrapped here to fit the page, nothing else is edited.

## The harness these snippets run in

Before any of the traps, the boring part, because two lines of it are the difference between a snippet that runs and a snippet that throws before it starts.

Every experiment is the body of a Vitest `it()`. Three small helpers sit at the top of the file:

```typescript
function log(label: string, obj: unknown) {
  console.log("[PROBE] " + label + " :: " + JSON.stringify(obj));
}

async function settle() {
  for (let i = 0; i < 5; i++) {
    await Promise.resolve();
    TestBed.tick();
  }
}

function tryRead(fn: () => unknown): unknown {
  try {
    return { ok: true, value: fn() };
  } catch (e: any) {
    return { ok: false, threw: e?.constructor?.name, message: e?.message };
  }
}
```

Each spec file uses its own prefix, `[PROBE]` here, `[H]` for the harness checks, `[REAL]` for the ones that talk to the real server and `[A]` for the old-option-name checks. It is the same one-line helper every time.

And the setup, which gives every snippet its `http`, its `ctrl` and its `injector`:

```typescript
describe("post snippets", () => {
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

  // every snippet below is the body of an it() in here
});
```

**`injector` is not optional.** `rxResource()` needs an injection context. A bare call outside a component does not misbehave quietly. It throws before your probe ever runs:

```typescript
let threw = "",
  message = "";
try {
  rxResource({ params: () => 1, stream: () => of(1) });
} catch (e: any) {
  threw = e?.constructor?.name;
  message = String(e?.message).slice(0, 120);
}
log("no-injector", { threw, message });
```

```text
[H] no-injector :: {"threw":"RuntimeError",
  "message":"NG0203: rxResource() can only be used within an injection context
  such as a constructor, a factory function, a field ini"}
```

**`TestBed.tick()` is the other one.** `params` is effect-scheduled, so nothing goes out on the wire until Angular flushes effects. Count the open requests before and after:

```typescript
const res = rxResource({
  params: () => "usr_123",
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
  injector,
});

const before = ctrl.match(() => true).length;
TestBed.tick();
const after = ctrl.match(() => true).length;

log("params-effect-scheduled", {
  openRequestsBeforeTick: before,
  afterTick: after,
});
```

```text
[PROBE] params-effect-scheduled :: {"openRequestsBeforeTick":0,"afterTick":1}
```

Zero, then one. That is why every snippet below ticks before it answers a request, and calls `await settle()` afterwards to let the resource catch up.

Those three steps land in the same order in almost every trap below, wrapped around the same failing response. **Call it the ritual:**

```typescript
TestBed.tick(); // let the params effect fire
ctrl
  .expectOne("/api/users/usr_123")
  .flush({ message: "boom" }, { status: 500, statusText: "Server Error" });
await settle(); // let the resource catch up before the probe reads it
```

When a snippet below says "the ritual", it means exactly that block. Anything a snippet changes about it, a different URL or a different response, is written out on the spot.

## First, the rename that breaks every example you copy

Every `rxResource` snippet written for Angular 19 looks like this:

```typescript
import { Component, inject, signal } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { rxResource } from "@angular/core/rxjs-interop";

interface User {
  id: string;
  name: string;
  role: string;
}

@Component({ selector: "app-old-api", template: "" })
export class OldApi {
  private http = inject(HttpClient);
  userId = signal("usr_123");
  userResource = rxResource({
    request: () => this.userId(),
    loader: ({ request }) => this.http.get<User>(`/api/users/${request}`),
  });
}
```

Paste it into Angular 22 and ask the compiler directly:

```bash
npx tsc -p tsconfig.app.json --noEmit
```

```text
src/app/old-api.ts(12,5): error TS2769: No overload matches this call.
  Overload 1 of 2, '(opts: RxResourceOptions<unknown, unknown> & { defaultValue: unknown; }): ResourceRef<unknown>', gave the following error.
    Object literal may only specify known properties, and 'request' does not exist in type 'RxResourceOptions<unknown, unknown> & { defaultValue: unknown; }'.
  Overload 2 of 2, '(opts: RxResourceOptions<unknown, unknown>): ResourceRef<unknown>', gave the following error.
    Object literal may only specify known properties, and 'request' does not exist in type 'RxResourceOptions<unknown, unknown>'.
src/app/old-api.ts(13,16): error TS7031: Binding element 'request' implicitly has an 'any' type.
```

Line 12 is `request`, line 13 is `loader`. `request` is now `params`, and `loader` is now `stream`. Same code, two words changed:

```typescript
userResource = rxResource({
  params: () => this.userId(),
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`),
});
```

The two old names do not fail the same way, and it is worth knowing which one leaves a mark. If you cast past the compiler, `request` still works, because `rxResource` still reads it. `loader` does not, and the failure is silent until you read the status. So force both past the type checker and look:

```typescript
let loaderCalled = 0;

const withLoader = rxResource<string, number>({
  params: () => 1,
  loader: () => {
    loaderCalled++;
    return of("from-loader");
  },
  injector,
} as any);
await settle();

log("runtime-loader-alias", {
  loaderCalled,
  status: withLoader.status(),
  error: (withLoader.error() as any)?.message?.slice(0, 60),
});
```

```text
[A] runtime-loader-alias :: {"loaderCalled":0,"status":"error",
  "error":"NG0990: Must provide `stream` option."}
```

Your loader is never called at all. **If you see `NG0990` in a console, you have an Angular 19 example in your codebase.**

The rename is not cosmetic either. **`loader` promised one value. `stream` means Angular listens to every emission.** That single word explains most of what follows, so it is the next thing to measure.

## A stream keeps talking

`loader` ran once and handed back one value. `stream` subscribes and stays subscribed, which means the resource can change under you after it has already resolved.

That matters the moment your source is anything other than a single HTTP call. A `Subject` in a service, a WebSocket, a poll: all of them emit again, and any of them can fail long after your value landed. So drive a resource from a `Subject` and read it after every step:

```typescript
const subj = new Subject<number>();
const res = rxResource<number, number>({
  params: () => 1,
  stream: () => subj.asObservable(),
  defaultValue: -1,
  injector,
});
await settle();
const before = { status: res.status(), value: res.value() };

subj.next(10);
await settle();
const first = { status: res.status(), value: res.value() };

subj.next(20);
await settle();
const second = { status: res.status(), value: res.value() };

subj.error(new Error("late failure"));
await settle();
const afterErr = {
  status: res.status(),
  value: tryRead(() => res.value()),
  error: (res.error() as any)?.message,
};

log("multi-emit", { before, first, second, afterErr });
```

```text
[PROBE] multi-emit :: {"before":{"status":"loading","value":-1},
  "first":{"status":"resolved","value":10},
  "second":{"status":"resolved","value":20},
  "afterErr":{"status":"error",
    "value":{"ok":false,"threw":"ResourceValueError",
      "message":"Resource is currently in an error state (see Error.cause for details): late failure"},
    "error":"late failure"}}
```

`10` arrives and the resource resolves. `20` arrives and quietly replaces it, with no reload and no `params` change. Then one late error, and the value you had is simply gone: the status flips to `'error'` and reading `value()` throws.

**A resource holds whatever the stream said last.** That is exactly how the next two traps work. They change what the stream says, so they change what the resource believes.

## Trap one: catching the error and returning a fallback

This is the code I wrote, and probably the code you wrote:

```typescript
const res = rxResource({
  params: () => "usr_123",
  stream: ({ params }) =>
    http.get<User>(`/api/users/${params}`).pipe(
      catchError(() => of(null)), // the trap
    ),
  injector,
});

// the ritual, unchanged: tick, flush the 500, settle

log("catchError-of-null", {
  status: res.status(),
  value: res.value(),
  error: res.error(),
  hasValue: res.hasValue(),
});
```

The response is a `500` with body `{"message":"boom"}`, and the probe says:

```text
[PROBE] catchError-of-null :: {"status":"resolved","value":null,"hasValue":true}
```

`error` is missing from that line because it was `undefined` and `JSON.stringify` drops those keys.

`catchError` did exactly what it promises. It caught the error and emitted `null` as a completely ordinary value. From the resource's side, **nothing went wrong**, so the status is `'resolved'` and your `@case ('error')` branch never runs.

It is the difference between a smoke alarm that is silent because there is no fire, and one that is silent because you took the battery out.

Look at `hasValue: true`. **`null` is a value.** `hasValue()` answers "did something arrive", not "is it any good", so the empty card renders happily on top of a burning server.

## Trap two: catching the error and returning nothing

So emit nothing at all. `EMPTY` completes without ever producing a value:

```typescript
const res = rxResource({
  params: () => "usr_123",
  stream: ({ params }) =>
    http.get<User>(`/api/users/${params}`).pipe(catchError(() => EMPTY)),
  injector,
});

// the ritual, unchanged: tick, flush the same 500, settle

const err = res.error();
log("catchError-EMPTY", {
  status: res.status(),
  errCtor: err?.constructor?.name,
  errMessage: err?.message,
});
```

I assumed this would hang on `'loading'` forever. It does not:

```text
[PROBE] catchError-EMPTY :: {"status":"error","errCtor":"RuntimeError",
  "errMessage":"NG0991: Resource completed before producing a value"}
```

You do get an error state. But the error is Angular's own complaint that the stream ended early, **not your server's**. The status code, the response body, the URL, all gone.

You swapped a silent success for a useless failure. That is arguably the worse trade.

## Two more traps that read as UI bugs

Before the rule that fixes the two above, two traps that never look like error handling at all. They arrive as bug reports about the interface.

**Your list flickers empty on refresh.** Both of these refetch, and only one of them keeps what is on screen. Which one you picked decides whether the user watches their table blink out and come back:

```typescript
const userId = signal("a");
const res = rxResource({
  params: () => userId(),
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
  injector,
});

TestBed.tick();
ctrl.expectOne("/api/users/a").flush({ id: "a", name: "Ada", role: "dev" });
await settle();

res.reload(); // path A
TestBed.tick();
const duringReload = { status: res.status(), value: res.value() };
ctrl.expectOne("/api/users/a").flush({ id: "a", name: "Ada", role: "dev" });
await settle();

userId.set("b"); // path B
TestBed.tick();
const duringLoad = { status: res.status(), value: res.value() };

log("loading-vs-reloading", { duringReload, duringLoad });
```

```text
[PROBE] loading-vs-reloading :: {
  "duringReload":{"status":"reloading","value":{"id":"a","name":"Ada","role":"dev"}},
  "duringLoad":{"status":"loading"}}
```

`value` is missing from `duringLoad` because changing `params` wiped it. **`loading` clears your plate before bringing the new one. `reloading` leaves it there until the new one lands.** Pick the one you meant.

**Your retry button has no spinner.** That is the same pair seen from the other side. After a failure there is no old value left to protect, so you would expect `reload()` to report `'loading'`, and a spinner keyed on that status to appear. Fail a request, hit reload, read the status:

```typescript
const res = rxResource({
  params: () => "x",
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
  injector,
});

// the ritual, with params "x", so the 500 lands on /api/users/x

const reloadReturn = res.reload();
TestBed.tick();

log("reload-after-error", {
  reloadReturn,
  status: res.status(),
  isLoading: res.isLoading(),
});
```

```text
[PROBE] reload-after-error :: {"reloadReturn":true,"status":"reloading","isLoading":true}
```

`'reloading'`, with nothing to reload. The user hits retry and your spinner never appears. **So key spinners on `isLoading()`**, which is `true` for both.

## The rule: let the error escape

Back to the two `catchError` traps. They have the same cause. `catchError` consumes the error, and a consumed error never reaches the resource. So stop consuming it:

```typescript
const res = rxResource({
  params: () => "usr_123",
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
  injector,
});

// the ritual, tick and settle included, but with a louder response:
ctrl
  .expectOne("/api/users/usr_123")
  .flush(
    { message: "Database is on fire" },
    { status: 500, statusText: "Internal Server Error" },
  );

// error() is typed Error | undefined, so narrow before reading HTTP fields.
const err = res.error();
const httpErr = err instanceof HttpErrorResponse ? err : null;

log("bubble", {
  status: res.status(),
  httpStatus: httpErr?.status,
  statusText: httpErr?.statusText,
  body: httpErr?.error,
});
```

```text
[PROBE] bubble :: {"status":"error","httpStatus":500,
  "statusText":"Internal Server Error","body":{"message":"Database is on fire"}}
```

Status code, status text, and the parsed body all survive. The narrowing in there is not decoration, and the next section is about why it is not optional.

**If you only wanted to log the error, use `tap` instead.** `tap` watches it go past without eating it. Here it bumps a counter so the probe can prove it fired exactly once, but in real code that line is your logger:

```typescript
let logged = 0;

const res = rxResource({
  params: () => "usr_123",
  stream: ({ params }) =>
    http.get<User>(`/api/users/${params}`).pipe(tap({ error: () => logged++ })),
  injector,
});

// the ritual, tick and settle included, but a 503 this time:
ctrl
  .expectOne("/api/users/usr_123")
  .flush({ m: 1 }, { status: 503, statusText: "Unavailable" });

const err = res.error();
log("tap-error", {
  logged,
  status: res.status(),
  httpStatus: err instanceof HttpErrorResponse ? err.status : undefined,
});
```

```text
[PROBE] tap-error :: {"logged":1,"status":"error","httpStatus":503}
```

Logged once, still an error, still carrying the 503.

## The error you catch is not an Error

Since Angular 20, `error()` is typed `Signal<Error | undefined>`. So an `instanceof Error` check should be safe. Ask that same error what it actually is:

```typescript
// same resource, same 500 as the bubble probe above
const err = res.error();
log("error-instanceof", {
  isHttpErrorResponse: err instanceof HttpErrorResponse,
  isErrorInstance: err instanceof Error,
});
```

```text
[PROBE] error-instanceof :: {"isHttpErrorResponse":true,"isErrorInstance":false}
```

`HttpErrorResponse` _implements_ `Error` but _extends_ `HttpResponseBase`. It quacks like an `Error` without being one, so `instanceof Error` is `false`.

Angular hands it to you anyway. It checks the shape, not the family tree. Anything with a string `name` and a string `message` is close enough.

So what happens to something that is not close enough? This matters because whatever comes back is the object your error banner has to read. Throw a bare string out of the `stream` and look at what `error()` holds:

```typescript
const res = rxResource({
  params: () => 1,
  stream: () => throwError(() => "just a string"),
  injector,
});
await settle();

const err: any = res.error();
log("non-error-throw", {
  status: res.status(),
  ctor: err?.constructor?.name,
  message: err?.message,
  cause: err?.cause,
});
```

```text
[PROBE] non-error-throw :: {"status":"error","ctor":"ResourceWrappedError",
  "message":"Resource returned an error that's not an Error instance: just a string.
  Check this error's .cause for the actual error.","cause":"just a string"}
```

**Anything that fails the shape check gets boxed in a `ResourceWrappedError`**, and your real error is on `.cause`. Angular even says so in the message.

**That shape check is newer than most articles about it.** Older Angular used a strict `instanceof Error`, which wrapped every single `HttpErrorResponse`. Every version is on npm, so there is no need to guess where it changed:

```bash
for v in 21.0.3 21.0.4 21.1.0; do
  npm i @angular/core@$v --ignore-scripts --silent
  grep -qh isErrorLike node_modules/@angular/core/fesm2022/*.mjs \
    && echo "$v: shape check" || echo "$v: instanceof only"
done
```

```text
21.0.3: instanceof only
21.0.4: shape check
21.1.0: shape check
```

**From 21.0.4 onward, your `HttpErrorResponse` arrives intact.** On 20.x and anything below 21.0.4, it is wrapped and you need `.cause`. If you are on 21.0.x, that is a one-patch bump.

So the narrowing helper still earns its place, just for a plainer reason:

```typescript
readonly httpError = computed(() => {
  const err = this.userResource.error();
  return err instanceof HttpErrorResponse ? err : null;
});
```

## value() does not return undefined. It throws.

The `ResourceStatus` docs say, word for word, that in the error state "`value()` will be `undefined`". Your template reads `value()` on every change detection pass, so the difference between `undefined` and a thrown exception is the difference between an empty card and a blank page. Read it in that state and see:

```typescript
const res = rxResource({
  params: () => "usr_123",
  stream: ({ params }) => http.get<User>(`/api/users/${params}`),
  injector,
});

// the ritual: tick, flush a 500, settle

try {
  res.value();
} catch (e: any) {
  log("value-in-error-state", {
    threw: true,
    ctor: e?.constructor?.name,
    causeCtor: e?.cause?.constructor?.name,
  });
}
```

```text
[PROBE] value-in-error-state :: {"threw":true,"ctor":"ResourceValueError",
  "causeCtor":"HttpErrorResponse"}
```

It throws. The real error is on `.cause`, and `ResourceValueError` is not exported, so you cannot even catch it by type.

**Ask `hasValue()` first.** It is a real type guard, so inside it the value is not optional:

{% raw %}

```html
@if (userResource.hasValue()) {
<h2>{{ userResource.value().name }}</h2>
}
```

{% endraw %}

Notice there is no `?.` in there. Inside that guard `value()` cannot be `undefined`, and the build agrees:

```bash
npx ng build --configuration development
```

```text
Application bundle generation complete. [1.900 seconds] - 2026-08-26T20:45:45.025Z
```

Drop the `@if` and the same build says:

{% raw %}

```text
Application bundle generation failed. [1.792 seconds] - 2026-08-26T20:45:54.357Z

✘ [ERROR] TS2532: Object is possibly 'undefined'. [plugin angular-compiler]

    src/app/tpl-noguard.ts:10:41:
      10 │   template: `<h2>{{ userResource.value().name }}</h2>`,
         ╵                                          ~~~~
```

{% endraw %}

**The guard is the type check.** Leave it out and the compiler catches you, which is a much better place to find out than a blank page.

## It cancels for you

Here is the flip side. Every trap so far was `rxResource` hiding a failure from you. This one is `rxResource` preventing a failure instead.

Change `params` and the in-flight request is not just unsubscribed, **the socket actually closes.** That is the difference between a search box that drops the work it no longer needs and one that leaves every abandoned query running against your database.

Proving it needs a server willing to tell you. The lab runs `api-server.mjs`, thirty lines of Node on port 4300, started with `node api-server.mjs` next to the tests. The line that matters is this one:

```javascript
req.on("aborted", () => console.log(`  !! ABORTED BY CLIENT: ${req.url}`));
```

This experiment lives in its own spec file, because there is nothing to flush. It talks to the real server, so it waits on the clock instead:

```typescript
async function waitFor(pred: () => boolean, ms = 8000) {
  const start = Date.now();
  while (!pred()) {
    if (Date.now() - start > ms) throw new Error("timeout waiting for condition");
    await new Promise((r) => setTimeout(r, 25));
    TestBed.tick();
  }
  TestBed.tick();
}
```

Then point a resource at a deliberately slow endpoint, one that sleeps three seconds, and move its `params` signal three times, the way a search box would:

```typescript
const API = "http://localhost:4300";

const q = signal("a");
const res = rxResource({
  params: () => q(),
  stream: ({ params }) => http.get<any>(`${API}/api/slow?q=${params}`),
  injector,
});

const t0 = Date.now();
TestBed.tick();
await new Promise((r) => setTimeout(r, 400));
TestBed.tick();
q.set("ab");
TestBed.tick();
await new Promise((r) => setTimeout(r, 400));
TestBed.tick();
q.set("abc");
TestBed.tick();
await waitFor(() => !res.isLoading(), 15000);

log("real-abort-httpclient", {
  elapsedMs: Date.now() - t0,
  status: res.status(),
  value: res.value(),
});
```

```text
[REAL] real-abort-httpclient :: {"elapsedMs":3823,"status":"resolved",
  "value":{"q":"abc","at":1787777056146}}
```

And the server saw this:

```text
2026-08-26T20:44:12.330Z GET /api/slow?q=a
  !! ABORTED BY CLIENT: /api/slow?q=a
2026-08-26T20:44:12.745Z GET /api/slow?q=ab
  !! ABORTED BY CLIENT: /api/slow?q=ab
2026-08-26T20:44:13.145Z GET /api/slow?q=abc
```

Only the last survived. On my machine the whole thing took 3.8 seconds instead of nine. **No `switchMap` anywhere.**

`HttpClient` gets this for free. A raw `fetch` does not, so hand it the `abortSignal` that `stream` gives you:

```typescript
stream: ({ params, abortSignal }) =>
  from(fetch(`/api/slow?q=${params}`, { signal: abortSignal }).then((r) => r.json())),
```

Forget that option and the server logs no aborts at all. Here are both, back to back: two requests with `abortSignal`, then the same two without it.

```text
2026-08-26T20:44:16.154Z GET /api/slow?q=a
  !! ABORTED BY CLIENT: /api/slow?q=a
2026-08-26T20:44:16.558Z GET /api/slow?q=ab
2026-08-26T20:44:19.576Z GET /api/slow?q=a
2026-08-26T20:44:19.979Z GET /api/slow?q=ab
```

Same code, one missing option, and the abort line is gone. Every superseded request runs to completion and gets binned, while the component looks perfectly healthy.

## So, toSignal or rxResource?

Every trap above was an error trap. This last question decides whether you get a second chance at all.

Both turn an `Observable` into a signal, so people treat them as interchangeable. One measurement settles it. Build the same feature twice, let the first request fail, then ask for a different record:

```typescript
const idA = signal("bad");
const idB = signal("bad");

// toSignal: one long-lived pipeline
const viaSignal = toSignal(
  toObservable(idA, { injector }).pipe(
    switchMap((v) => http.get<User>(`/api/u/${v}`)),
  ),
  { injector },
);

// rxResource: one request per params value
const viaResource = rxResource({
  params: () => idB(),
  stream: ({ params }) => http.get<User>(`/api/v/${params}`),
  injector,
});

TestBed.tick();
ctrl.expectOne("/api/u/bad").flush({}, { status: 500, statusText: "e" });
ctrl.expectOne("/api/v/bad").flush({}, { status: 500, statusText: "e" });
await settle();

// both have failed on 'bad', now point both at 'good'
idA.set("good");
idB.set("good");
TestBed.tick();
await settle();

// ctrl is the HttpTestingController; match() counts requests actually issued
log("recovery", {
  toSignal: { refetched: ctrl.match("/api/u/good").length },
  rxResource: { refetched: ctrl.match("/api/v/good").length },
});
```

```text
[PROBE] recovery :: {"toSignal":{"refetched":0},"rxResource":{"refetched":1}}
```

`refetched: 0`. **An RxJS error terminates the stream permanently.** The user picks a different record and the screen stays stuck on the old error forever, with no network traffic at all.

That is the dangerous part. There is nothing in the network tab to inspect, because nothing was ever sent. `rxResource` treats every `params` value as a brand new request, so it just recovers.

That is the whole difference in one sentence: **`toSignal` models a value, `rxResource` models a request.** A request can be pending, can fail, and can be retried. A value cannot.

- **`rxResource` when you are fetching.** Anything with reactive parameters, anything that can fail, anything that needs a spinner.
- **`toSignal` when you are adapting** something that already exists and cannot fail: a `BehaviorSubject` in a service, router params, a third-party observable. If that source always has a value, add `requireSync: true`. The `undefined` disappears from the type.
- If you find yourself building a `{ loading, value, error }` union around a `toSignal`, stop. You are rewriting `rxResource` by hand.

## Summary

- **`rxResource()` needs an injection context.** Outside a component or a field initialiser, pass `injector` or you get `NG0203`.
- **Use `params` and `stream`.** Every Angular 19 example you copy will fail to compile, and a stray `loader` is never called at all.
- **It is a stream.** A late emission overwrites your value, and a late error throws it away.
- **Never `catchError(() => of(fallback))`** unless you want that fallback treated as a success. `hasValue()` returns `true` even for `null`.
- **Never `catchError(() => EMPTY)`.** You get NG0991 instead of your server's actual error.
- **`reload()` keeps the old value, changing `params` clears it.** Key spinners on `isLoading()`.
- **Let errors escape the stream.** Use `tap({ error })` when you only want to log.
- **`HttpErrorResponse` is not an `Error`**, and it only arrives unwrapped from **Angular 21.0.4** onward. Below that, look in `.cause`.
- **Guard with `hasValue()`.** In the error state `value()` throws, whatever the status docs claim.
- **Changing `params` cancels the old request on the wire.** No `switchMap` needed, and a raw `fetch` needs the `abortSignal` handed to it.
- **`toSignal` cannot recover from an error, `rxResource` can.** If you are fetching, reach for `rxResource`.

**Every time you write `catchError` inside a `stream`, ask one question: what is the resource supposed to learn from this?** If the answer is "nothing", you have not handled the error. You have hidden it.
