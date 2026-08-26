---
# SEO Target Queries:
#   Google: "angular rxresource error", "angular rxresource error handling", "angular rxresource vs resource"
#   Bing:   "angular rxresource handle error", "angular rxresource vs"
#   Also:   "angular tosignal vs rxresource", "angular tosignal or rxresource"
tags: ["typescript", "angular", "signals", "rxresource", "error-handling"]
categories: ["typescript", "angular"]
title: "Angular rxResource Error Handling: catchError Lies to You"
image:
  path: /assets/img/2026-08-19/main.jpg
  alt: A safety net that catches everything and reports absolutely nothing.
published: false
---

I love `catchError`. It is also the operator that told me a 500 was a success.

I moved a data-fetching pipeline over to `rxResource`, kept my usual `.pipe(catchError(...))` safety net, and pointed it at an endpoint that returns a 500. No error banner. `error()` was `undefined`. `status()` said `'resolved'`.

The safety net was the thing hiding the fire.

Every log line below came out of a throwaway Angular 22.1.3 project, so you can trust them even where they contradict the docs. And a few of them do. The probe is just this, sitting at the top of a Vitest spec:

```typescript
function log(label: string, obj: unknown) {
  console.log('[PROBE] ' + label + ' :: ' + JSON.stringify(obj));
}
```

Long lines are wrapped here to fit the page, nothing else is edited.

## First, the rename that breaks every example you copy

Every `rxResource` snippet written for Angular 19 looks like this:

```typescript
userResource = rxResource({
  request: () => this.userId(),
  loader: ({ request }) => this.http.get<User>(`/api/users/${request}`),
});
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

`request` is now `params`, and `loader` is now `stream`. Same code, two words changed:

```typescript
userResource = rxResource({
  params: () => this.userId(),
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`),
});
```

The rename is not cosmetic. **`loader` promised one value. `stream` means Angular listens to every emission.** That single word explains most of what follows.

## Trap one: catching the error and returning a fallback

This is the code I wrote, and probably the code you wrote:

```typescript
const res = rxResource({
  params: () => 'usr_123',
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`).pipe(
    catchError(() => of(null)),   // the trap
  ),
});

log('catchError-of-null', {
  status: res.status(),
  value: res.value(),
  error: res.error(),
  hasValue: res.hasValue(),
});
```

The server answers `500 {"message":"boom"}`, and the probe says:

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
  params: () => 'usr_123',
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`).pipe(
    catchError(() => EMPTY),
  ),
});

const err = res.error();
log('catchError-EMPTY', {
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

## The rule: let the error escape

Both traps have the same cause. `catchError` consumes the error, and a consumed error never reaches the resource. So stop consuming it:

```typescript
const res = rxResource({
  params: () => 'usr_123',
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`),
});

// error() is typed Error | undefined, so narrow before reading HTTP fields.
// The next section is about why that is not optional.
const err = res.error();
const httpErr = err instanceof HttpErrorResponse ? err : null;

log('bubble', {
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

Status code, status text, and the parsed body all survive.

**If you only wanted to log the error, use `tap` instead.** `tap` watches it go past without eating it. Here it bumps a counter so the probe can prove it fired exactly once, but in real code that line is your logger:

```typescript
let logged = 0;

const res = rxResource({
  params: () => 'usr_123',
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`).pipe(
    tap({ error: () => logged++ }),
  ),
});

const err = res.error();
log('tap-error', {
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
const err = res.error();
log('error-instanceof', {
  isHttpErrorResponse: err instanceof HttpErrorResponse,
  isErrorInstance: err instanceof Error,
});
```

```text
[PROBE] error-instanceof :: {"isHttpErrorResponse":true,"isErrorInstance":false}
```

`HttpErrorResponse` *implements* `Error` but *extends* `HttpResponseBase`. It quacks like an `Error` without being one, so `instanceof Error` is `false`.

Angular hands it to you anyway, because internally it checks the shape instead of the family tree: anything with a string `name` and a string `message` is close enough. Anything else gets wrapped in a box you have to open with `.cause`.

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

The `ResourceStatus` docs say, word for word, that in the error state "`value()` will be `undefined`". So read it in that state and see:

```typescript
try {
  res.value();
} catch (e: any) {
  log('value-in-error-state', {
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

Notice there is no `?.` in there. The compiler is happy, because inside that guard `value()` cannot be `undefined`.

## Two smaller traps that look like UI bugs

**Your list flickers empty on refresh.** Both of these refetch, and only one of them keeps what is on screen:

```typescript
res.reload();                                                  // path A
TestBed.tick();
const duringReload = { status: res.status(), value: res.value() };

userId.set('b');                                               // path B
TestBed.tick();
const duringLoad = { status: res.status(), value: res.value() };

log('loading-vs-reloading', { duringReload, duringLoad });
```

```text
[PROBE] loading-vs-reloading :: {
  "duringReload":{"status":"reloading","value":{"id":"a","name":"Ada","role":"dev"}},
  "duringLoad":{"status":"loading"}}
```

`value` is missing from `duringLoad` because changing `params` wiped it. **`loading` clears your plate before bringing the new one. `reloading` leaves it there until the new one lands.** Pick the one you meant.

**Your retry button has no spinner.** After a failure, `reload()` goes to `'reloading'`, not `'loading'`, even though there is no old value to preserve. So key spinners on `isLoading()`, which covers both.

## It cancels for you

This one is a genuine gift. Change `params` and the in-flight request is not just unsubscribed, **the socket actually closes.**

Proving that needs a server willing to tell you, which is one line of Node:

```javascript
req.on('aborted', () => console.log(`  !! ABORTED BY CLIENT: ${req.url}`));
```

Then point a resource at a deliberately slow endpoint and type three characters into it:

```typescript
const q = signal('a');
const res = rxResource({
  params: () => q(),
  stream: ({ params }) => this.http.get(`/api/slow?q=${params}`),
});

q.set('ab');    // 400ms later
q.set('abc');   // 400ms after that
```

The server saw this:

```text
2026-08-26T18:39:20.114Z GET /api/slow?q=a
  !! ABORTED BY CLIENT: /api/slow?q=a
2026-08-26T18:39:20.523Z GET /api/slow?q=ab
  !! ABORTED BY CLIENT: /api/slow?q=ab
2026-08-26T18:39:20.924Z GET /api/slow?q=abc
```

Only the last survived, and the whole thing took 3.8 seconds instead of nine. **No `switchMap` anywhere.**

`HttpClient` gets this for free. A raw `fetch` does not, so hand it the `abortSignal` that `stream` gives you:

```typescript
stream: ({ params, abortSignal }) =>
  from(fetch(`/api/slow?q=${params}`, { signal: abortSignal }).then((r) => r.json())),
```

Forget that option and the server logs no aborts at all. Every superseded request runs to completion and gets binned, while the component looks perfectly healthy.

## So, toSignal or rxResource?

Both turn an `Observable` into a signal, so people treat them as interchangeable. One measurement settles it. Build the same feature twice, let the first request fail, then ask for a different record:

```typescript
// toSignal: one long-lived pipeline
const viaSignal = toSignal(
  toObservable(idA).pipe(switchMap((v) => this.http.get<User>(`/api/u/${v}`))),
);

// rxResource: one request per params value
const viaResource = rxResource({
  params: () => idB(),
  stream: ({ params }) => this.http.get<User>(`/api/v/${params}`),
});

// both fail on 'bad', then both are pointed at 'good'
idA.set('good');
idB.set('good');

log('recovery', {
  toSignal:   { refetched: ctrl.match('/api/u/good').length },
  rxResource: { refetched: ctrl.match('/api/v/good').length },
});
```

```text
[PROBE] recovery :: {"toSignal":{"refetched":0},"rxResource":{"refetched":1}}
```

`refetched: 0`. **An RxJS error terminates the stream permanently.** The user picks a different record and the screen stays stuck on the old error forever, with no network traffic at all. I have shipped this bug. `rxResource` treats every `params` value as a brand new request, so it just recovers.

That is the whole difference in one sentence: **`toSignal` models a value, `rxResource` models a request.** A request can be pending, can fail, and can be retried. A value cannot.

- **`rxResource` when you are fetching.** Anything with reactive parameters, anything that can fail, anything that needs a spinner.
- **`toSignal` when you are adapting** something that already exists and does not fail: a `BehaviorSubject` in a service, router params, a third-party observable. Add `requireSync: true` when the source always has a value and you get `Signal<T>` with no `undefined` in the type.
- If you find yourself building a `{ loading, value, error }` union around a `toSignal`, stop. You are rewriting `rxResource` by hand.

## Summary

- **Use `params` and `stream`.** Every Angular 19 example you copy will fail to compile.
- **Never `catchError(() => of(fallback))`** unless you want that fallback treated as a success. `hasValue()` returns `true` even for `null`.
- **Never `catchError(() => EMPTY)`.** You get NG0991 instead of your server's actual error.
- **Let errors escape the stream.** Use `tap({ error })` when you only want to log.
- **`HttpErrorResponse` is not an `Error`**, and it only arrives unwrapped from **Angular 21.0.4** onward. Below that, look in `.cause`.
- **Guard with `hasValue()`.** In the error state `value()` throws, whatever the status docs claim.
- **`reload()` keeps the old value, changing `params` clears it.** Key spinners on `isLoading()`.
- **It is a stream.** A late emission overwrites your value, and a late error throws it away.

And the friendly tip to finish on: **the moment you write `catchError` inside a `stream`, ask yourself what the resource is supposed to learn from it.** If the answer is "nothing", you have not handled the error. You have hidden it.
