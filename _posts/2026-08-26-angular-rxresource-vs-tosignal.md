---
# SEO Target Queries:
#   Google: "angular rxresource vs tosignal", "angular tosignal error handling", "rxresource error handling"
#   Bing:   "tosignal vs rxresource", "angular signal http error", "rxresource catcherror"
tags: ["typescript", "angular", "signals", "rxresource", "tosignal", "error-handling"]
categories: ["typescript", "angular"]
title: "Angular rxResource vs toSignal: Fetching Data and Catching Errors"
image:
  path: /assets/img/2026-08-26/main.jpg
  alt: Two safety nets. One of them has a hole you cannot see from here.
---

`rxResource` and `toSignal` live in the same package, take the same input, and hand you back the same thing: a signal. So most people treat them as two spellings of one idea and pick whichever they saw first.

Then a request returns a 500, and they stop being the same thing at all.

This post runs both of them at the same failing endpoint and writes down exactly what happens. Every log line below came out of a test run, not out of the docs — and a couple of them contradict the docs.

## The lab

A stock Angular project, nothing added:

```bash
npx @angular/cli@latest new rxres-demo --style=css --ssr=false --zoneless --defaults
```

That gives Angular **22.1.3**, TypeScript **6.0.3**, RxJS **7.8.2**, and Vitest **4.1.11** already wired up.

A "probe" is just a `console.log` with a prefix I can grep for:

```typescript
function log(label: string, obj: unknown) {
  console.log("[EXP] " + label + " :: " + JSON.stringify(obj));
}
```

`JSON.stringify` is deliberate. It puts a whole snapshot on one line, and it **drops any key whose value is `undefined`**. So when a field is missing from a log line below, that absence is the measurement, not a typo.

Long lines are wrapped to fit the page. Nothing else is edited.

---

## Chapter 1: The API moved under both of them

Before comparing behaviour, you need to know which version you are reading about, because both of these functions changed shape recently — and in `toSignal`'s case, the thing that changed is *specifically* the error handling.

I did not take this from release notes. Every version of `@angular/core` is on npm with its type definitions inside, so I downloaded eighteen of them and read the declarations.

### rxResource: two option names and a whole new status type

| Angular | Options | `status()` | `error()` | Stability |
| --- | --- | --- | --- | --- |
| 19.0 – 19.2 | `request` + `loader` | numeric enum (`Idle=0` … `Local=5`) | `Signal<unknown>` | experimental |
| 20.0 – 21.x | `params` + `stream` | string union (`'idle'` … `'local'`) | `Signal<Error \| undefined>` | experimental |
| 22.0+ | `params` + `stream` | string union | `Signal<Error \| undefined>` | **stable** |

Three separate breaking changes landed in Angular 20, which is why almost every `rxResource` article you find is wrong now.

Paste a typical Angular 19 snippet into an Angular 22 project and ask the compiler:

```typescript
userResource = rxResource({
  request: () => this.userId(),
  loader: ({ request }) => this.http.get<User>(`/api/users/${request}`),
});
```

```bash
npx tsc -p tsconfig.app.json --noEmit
```

```text
src/app/old-api.ts(14,5): error TS2769: No overload matches this call.
  Overload 2 of 2, '(opts: RxResourceOptions<unknown, unknown>): ResourceRef<unknown>',
    gave the following error.
    Object literal may only specify known properties, and 'request' does not
    exist in type 'RxResourceOptions<unknown, unknown>'.
src/app/old-api.ts(15,16): error TS7031: Binding element 'request' implicitly
    has an 'any' type.
```

Same code, two words changed:

```typescript
userResource = rxResource({
  params: () => this.userId(),
  stream: ({ params }) => this.http.get<User>(`/api/users/${params}`),
});
```

**The rename is not cosmetic.** `loader` promised one value and then it was done. `stream` means Angular keeps listening to every emission. That single word explains a lot of what happens later in this post.

The status change bites just as hard. On Angular 19 you wrote `status() === ResourceStatus.Error`, comparing against the number `1`. On Angular 20 and up you write `status() === 'error'`. Neither version compiles on the other.

And do not skip the stability column. `rxResource` was marked `@experimental` for three major versions and only became `@publicApi` in Angular 22. The `request` → `params` churn is exactly what that label was warning you about.

### toSignal: the error option was deleted

`toSignal` is older and looks calmer, but it had one change that matters more than anything on the `rxResource` list.

| Angular | Options | Stability |
| --- | --- | --- |
| 16.0 | `initialValue`, `requireSync`, `injector`, `manualCleanup` | developer preview |
| 17.0 | **+ `rejectErrors`** | developer preview |
| 18.2 | + `equal` | developer preview |
| 20.0 | **− `rejectErrors`** | **stable** |
| 22.1 | `initialValue`, `requireSync`, `injector`, `manualCleanup`, `equal` | stable |

`rejectErrors` was the only error-related knob `toSignal` ever had. Here is what its own documentation said, back in Angular 19:

> Whether `toSignal` should throw errors from the Observable error channel back to RxJS, where they'll be processed as uncaught exceptions. In practice, this means that the signal returned by `toSignal` will keep returning the last good value forever [...] This option emulates the behavior of the `async` pipe.

In Angular 20 that block is simply gone from the type. It is not deprecated, not renamed, not moved. Try it:

```typescript
user = toSignal(this.http.get<User>("/api/users/usr_123"), {
  rejectErrors: true,
});
```

```text
src/app/old-api.ts(20,5): error TS2769: No overload matches this call.
  The last overload gave the following error.
    Object literal may only specify known properties, and 'rejectErrors' does
    not exist in type 'NoInfer<ToSignalOptions<User>> & { initialValue: User; ... }'.
```

And it is not just missing from the types. It is gone from the shipped JavaScript too:

```bash
grep -r "rejectErrors" node_modules/@angular/core/
# (no output)
```

**So on Angular 20 and up, `toSignal` has exactly zero built-in options for dealing with a failure.** Whatever you want to do about errors, you do it inside the Observable, before `toSignal` ever sees it. Hold onto that — it is the reason Chapter 3 goes the way it does.

---

## Chapter 2: How each one asks for data

Both functions turn an `Observable` into a `Signal`. That is where the similarity stops, because they disagree about *who owns the request*.

### toSignal takes an Observable that already exists

```typescript
user = toSignal(this.http.get<User>("/api/users/usr_123"));
```

`toSignal` subscribes once and copies whatever comes out into a signal. It has no idea that a URL was involved. It does not know what a "request" is.

That sounds like a detail until you try to make it react to something. Here is the version almost everybody writes first:

```typescript
const id = signal("a");
const user = toSignal(http.get<User>("/api/u/" + id()));

id.set("b"); // surely this refetches?
```

```text
[EXP] acq-bare-toSignal :: {"urls":["/api/u/a"],"readAfterChange":{"ok":true}}
```

One URL in that list. One request, ever.

**`id()` was read once, while the string was being built, and the resulting Observable has no memory of where it came from.** Changing the signal afterwards does nothing at all — no error, no warning, no second request. The signal keeps whatever `a` returned, and your screen keeps showing it.

To get reactivity you have to build the plumbing yourself, with `toObservable` and `switchMap`:

```typescript
const user = toSignal(
  toObservable(id).pipe(switchMap((v) => http.get<User>("/api/s/" + v))),
);
```

### rxResource describes a request instead

```typescript
const user = rxResource({
  params: () => id(),
  stream: ({ params }) => http.get<User>("/api/r/" + params),
});
```

`params` is a reactive function. Angular tracks every signal you read inside it, and whenever one of them changes, it runs `stream` again with the new value.

Both approaches now refetch properly:

```text
[EXP] acq-refetch :: {"firstRound":["/api/s/a","/api/r/a"],
                      "secondRound":["/api/s/b","/api/r/b"]}
```

Both also cancel the request they superseded. `switchMap` does it for `toSignal`; `rxResource` does it because a new `params` value means the old request is irrelevant. Nobody wins that one.

### But only one of them can say "still loading"

This is the first real gap, and it shows up before any error does. Ask both of them what is going on while the request is still in the air:

```text
[EXP] acq-loading :: {"toSignalIsUndefined":true,
  "rxResource":{"status":"loading","isLoading":true,"hasValue":false}}
```

Notice `toSignalValue` is missing from that line entirely — because it was `undefined`, and `JSON.stringify` drops it.

**`toSignal` has one slot.** `undefined` in that slot means "still waiting", and it also means "the server sent me nothing", and it also means "I have not started". You cannot tell those apart, so a template can only say `@if (user()) { ... } @else { spinner }` and hope.

`rxResource` has a whole state machine next to the value:

```text
[EXP] acq-loaded :: {"toSignalValue":{"id":"x","name":"X"},
  "rxResource":{"status":"resolved","isLoading":false,"hasValue":true}}
```

**One sentence version: `toSignal` models a value, `rxResource` models a request.** A request can be pending, can fail, and can be retried. A value cannot.

---

## Chapter 3: Error handling, one experiment at a time

Here is what we actually want when a request fails. Two things, and you need both:

1. **Display it.** The user sees an error card instead of an empty one.
2. **Log it.** With the status code and the response body, so you can debug it later.

Eleven experiments follow. Each one gets a verdict, and — more usefully — an explanation of *why* it turned out that way.

One result up front that applies to every single experiment: I registered a custom `ErrorHandler` in the test module and counted its calls. It was called **zero times**, for both libraries, in every failing case:

```text
"globalErrorHandlerCalls":0
```

**Nothing tells you about a failed request except you.** Neither function shouts. If you do not write the logging line, the error is invisible.

### Experiment 1: toSignal with no error handling at all

```typescript
const user = toSignal(http.get<User>("/api/s/x"));
// server answers 500
```

```text
[EXP] err-toSignal-read :: {"globalErrorHandlerCalls":0,
  "firstRead":{"ok":false,"threw":"HttpErrorResponse",
    "message":"Http failure response for /api/s/x: 500 Server Error"},
  "secondRead":{"ok":false,"threw":"HttpErrorResponse",
    "message":"Http failure response for /api/s/x: 500 Server Error"}}
```

**Why it happened:** `toSignal` catches the error off the Observable's error channel and stores it. It cannot put it in the value slot, because the value slot holds values. So it holds onto the error and re-throws it at whoever reads the signal next. Forever — look at `secondRead`.

The error object itself is perfect. It is the real `HttpErrorResponse`, status code and all. The problem is *how* you get it: by reading a signal and having it explode.

Your template reads that signal during change detection. So the throw happens inside Angular's rendering, and there is no `@if` you can write to avoid it, because asking the question *is* the thing that throws.

**Verdict: fails both goals.** Nothing is logged, and the display does not degrade — it detonates.

### Experiment 2: toSignal with `tap({ error })` for logging

`tap` is the "look, don't touch" operator. It watches values and errors go past without consuming them.

```typescript
const logged: string[] = [];
const user = toSignal(
  http.get<User>("/api/s/x").pipe(tap({ error: (e) => logged.push(e.status) })),
);
```

```text
[EXP] err-toSignal-tap :: {"logged":["503"],
  "read":{"ok":false,"threw":"HttpErrorResponse",
    "message":"Http failure response for /api/s/x: 503 Unavailable"}}
```

**Why it happened:** `logged` has one entry, so the logging fired exactly once with the real status code. And because `tap` did not consume the error, it carried on down the pipe to `toSignal`, which still stores it and still throws.

That second half is a feature, not a bug — `tap` is the correct way to log in *both* libraries, and you will see it again in Experiment 9.

**Verdict: logging solved. Display still broken.**

### Experiment 3: toSignal + `catchError`, placed one line too high

Fine — stop the throw. `catchError` turns an error into a value:

```typescript
const user = toSignal(
  toObservable(id).pipe(
    switchMap((v) => http.get<User>("/api/s/" + v)),
    catchError(() => of(null)), // <- outside the switchMap
  ),
);
```

The read stops throwing. Now change `id` to a record that works:

```text
[EXP] err-catchError-outside :: {"afterError":{"ok":true,"value":null},
  "refetchedRequests":0,
  "finalRead":{"ok":true,"value":null}}
```

**`refetchedRequests: 0`.** No network activity at all. The user picks a different record and the screen stays blank forever.

**Why it happened:** this is the single most important RxJS rule in this post. **An Observable that errors is finished.** It is not paused, it is not retrying — it has terminated, permanently, and it will never emit again.

The error escaped the inner `http.get`, travelled up into the outer `toObservable(id)` pipeline, and killed it. `catchError` did catch it, but by then the damage was done: the pipeline that was supposed to be listening to `id` forever is dead. `id.set('good')` now shouts into a disconnected wire.

I have shipped this bug. It is invisible in testing, because you have to fail *first* and then succeed to see it.

**Verdict: fails, and fails silently, which is worse.**

### Experiment 4: the same `catchError`, one line lower

Move it inside the `switchMap` so it only ever sees one request's error:

```typescript
const user = toSignal(
  toObservable(id).pipe(
    switchMap((v) =>
      http.get<User>("/api/s/" + v).pipe(catchError(() => of(null))),
    ),
  ),
);
```

```text
[EXP] err-catchError-inside :: {"afterError":{"ok":true,"value":null},
  "refetchedRequests":1,
  "finalRead":{"ok":true,"value":{"id":"good","name":"Good"}}}
```

**Why it happened:** the inner Observable — the one `switchMap` created for this specific request — is the one that dies. The outer pipeline never sees an error, so it stays subscribed to `id`, and the next change starts a fresh inner Observable. Recovery works.

**Two identical lines of code, two characters of indentation apart, and one of them permanently breaks your feature.** If you remember one thing about `toSignal` error handling, make it this.

But we are still not done. The value is `null`, and `null` is what the code would also produce for "this user has no data". The screen can show an empty state, but it cannot show an *error* state, because that information was thrown in the bin the moment `catchError` returned `of(null)`.

**Verdict: recovery fixed, display still wrong.**

### Experiment 5: toSignal done properly

To keep the error you have to carry it in the value, which means the value is no longer a `User` — it is a little union describing everything that can be true:

```typescript
type State =
  | { kind: "loading" }
  | { kind: "value"; value: User }
  | { kind: "error"; error: HttpErrorResponse };

const state = toSignal(
  toObservable(id).pipe(
    switchMap((v) =>
      http.get<User>("/api/s/" + v).pipe(
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

```text
[EXP] err-toSignal-state-machine :: {"whileLoading":"loading",
  "errored":{"kind":"error","httpStatus":500},
  "refetchedRequests":1,
  "final":{"kind":"value","value":{"id":"good","name":"Good"}}}
```

**Why it happened:** everything is now explicit. `startWith` supplies the loading state that `toSignal` could never express. `catchError` is inside the `switchMap`, so recovery still works. And crucially it maps into a *tagged* error state rather than a fake success, so the distinction survives.

Note that this uses `catchError(() => of(...))` — the exact operator Experiment 3 blamed for everything. It is fine here. **The trap was never `catchError` itself; it was throwing away the difference between "failed" and "empty".**

**Verdict: passes both goals.** It also takes fifteen lines, three RxJS operators, a hand-written type, and correct operator placement. Keep that number in mind for the conclusion.

### Experiment 6: rxResource + `catchError(() => of(null))`

Switching sides. This is the code I wrote when I first moved a pipeline to `rxResource`, and probably the code you wrote:

```typescript
const res = rxResource({
  stream: () => http.get<User>("/api/r/x").pipe(catchError(() => of(null))),
});
```

The server answers 500. The probe says:

```text
[EXP] err-rxResource-of-null :: {"status":"resolved","value":null,
  "hasValue":true,"errorIsUndefined":true}
```

`status: 'resolved'`. `error` is `undefined`. **The resource believes everything went fine.**

**Why it happened:** `catchError` did exactly what it promises. It caught the error and emitted `null` as a completely ordinary value. From the resource's point of view a value arrived, so the request succeeded. Your `@case ('error')` branch never runs.

It is the difference between a smoke alarm that is silent because there is no fire, and one that is silent because you took the battery out.

And look at `hasValue: true`. **`null` is a value.** `hasValue()` answers "did something arrive", not "is it any good", so your empty card renders happily on top of a burning server.

**Verdict: fails, and actively lies about it.**

### Experiment 7: rxResource + `catchError(() => EMPTY)`

So emit nothing at all. `EMPTY` completes without ever producing a value:

```typescript
stream: () => http.get<User>("/api/r/x").pipe(catchError(() => EMPTY));
```

I assumed this would hang on `'loading'` forever. It does not:

```text
[EXP] err-rxResource-empty :: {"status":"error","errorCtor":"RuntimeError",
  "message":"NG0991: Resource completed before producing a value","cause":null}
```

**Why it happened:** you do get an error state — but the error is *Angular's* complaint that the stream ended without delivering anything. Your server's error was consumed by `catchError` and never reached the resource, so it could not be reported. The status code, the response body, the URL: all gone, and `cause` is empty too.

You swapped a silent success for a useless failure. Arguably the worse trade, because now you get a bug report saying "NG0991" and no idea which endpoint did it.

**Verdict: fails.**

### Experiment 8: rxResource with no `catchError` at all

Both traps have the same cause: `catchError` consumes the error, and a consumed error never reaches the resource. So stop consuming it.

```typescript
const res = rxResource({
  stream: () => http.get<User>("/api/r/x"),
});
```

```text
[EXP] err-rxResource-bubble :: {"globalErrorHandlerCalls":0,"status":"error",
  "httpStatus":500,"statusText":"Internal Server Error","url":"/api/r/x",
  "body":{"message":"Database is on fire"}}
```

**Why it happened:** this is the thing `rxResource` is built to do. It subscribes to your stream and treats the error channel as one of the legitimate outcomes of a request, so it captures the error object into `error()` and flips `status()` to `'error'`.

Status code, status text, URL, and the parsed response body all survive intact. You can put any of them on screen.

**Verdict: display solved, with four lines of code and zero operators.**

### Experiment 9: rxResource + `tap({ error })` for logging

Same fix as Experiment 2, same reason. `tap` watches without eating:

```typescript
stream: () => http.get<User>("/api/r/x").pipe(tap({ error: () => logged++ })),
```

```text
[EXP] err-rxResource-tap :: {"logged":1,"status":"error","httpStatus":503}
```

Logged exactly once, still an error, still carrying the 503.

**Verdict: both goals passed.** This is the whole recipe: let the error escape, and use `tap` if you also want to log it.

> The moment you type `catchError` inside a `stream`, ask yourself what the resource is supposed to learn from it. If the answer is "nothing", you have not handled the error — you have hidden it.
{: .prompt-tip }

### Experiment 10: three gotchas while reading the error

The error is captured, but getting it onto the screen has three sharp edges.

**Sharp edge one: the error is not an `Error`.**

Since Angular 20, `error()` is typed `Signal<Error | undefined>`, so an `instanceof Error` check looks safe. Ask the object what it actually is:

```text
[EXP] err-rxResource-instanceof :: {"isHttpErrorResponse":true,
  "isErrorInstance":false,"ctorName":"HttpErrorResponse",
  "name":"HttpErrorResponse"}
```

`HttpErrorResponse` *implements* `Error` but *extends* `HttpResponseBase`. It quacks like an `Error` without being one, so `instanceof Error` is `false` even though the type says otherwise.

Angular hands it to you anyway, because internally it checks the shape rather than the family tree. This is the actual code, from `@angular/core@21.0.4`:

```javascript
function isErrorLike(error) {
  return (
    error instanceof Error ||
    (typeof error === "object" &&
      typeof error.name === "string" &&
      typeof error.message === "string")
  );
}
```

**That shape check is newer than most articles about it.** Angular 21.0.3 and everything below it used a strict `instanceof Error`, which wrapped every single `HttpErrorResponse` in a `ResourceWrappedError` and buried the real one on `.cause`. Every version is on npm, so there is no need to guess:

```bash
for v in 21.0.3 21.0.4 21.1.0; do
  npm i @angular/core@$v --ignore-scripts --silent
  grep -qrh isErrorLike node_modules/@angular/core/fesm2022/ \
    && echo "$v: shape check" || echo "$v: instanceof only"
done
```

```text
21.0.3: instanceof only
21.0.4: shape check
21.1.0: shape check
```

**From 21.0.4 onward your `HttpErrorResponse` arrives intact.** Below that, look in `.cause`. If you are on 21.0.x, that is a one-patch bump.

Either way, narrow before you read HTTP fields:

```typescript
readonly httpError = computed(() => {
  const err = this.userResource.error();
  return err instanceof HttpErrorResponse ? err : null;
});
```

**Sharp edge two: `value()` does not return `undefined` in the error state. It throws.**

The `ResourceStatus` docs say, word for word, that in the error state "`value()` will be `undefined`". Read it in that state and see:

```text
[EXP] err-value-throws :: {"hasValue":false,
  "read":{"ok":false,"threw":"ResourceValueError",
    "message":"Resource is currently in an error state (see Error.cause for
      details): Http failure response for /api/r/x: 500 e"},
  "causeCtor":"HttpErrorResponse"}
```

It throws a `ResourceValueError`, which is not exported, so you cannot even catch it by type. The real error is on `.cause`.

**Sharp edge three: ask `hasValue()` first.** It is a real type guard, so inside it the value is not optional:

{% raw %}

```html
@if (userResource.hasValue()) {
  <h2>{{ userResource.value().name }}</h2>
} @else if (userResource.error()) {
  <p class="error">Could not load: {{ httpError()?.status }}</p>
} @else {
  <p>Loading…</p>
}
```

{% endraw %}

Notice there is no `?.` on `value()`. The compiler is happy, because inside that guard `value()` cannot be `undefined`.

### Experiment 11: what happens after the error

The last question nobody asks until a support ticket arrives: can the user get out of the error state?

Point both at a broken record, let both fail, then point both at a good one:

```text
[EXP] err-recovery :: {
  "toSignal":{"refetchedRequests":0,
    "read":{"ok":false,"threw":"HttpErrorResponse",
      "message":"Http failure response for /api/s/bad: 500 e"}},
  "rxResource":{"refetchedRequests":1,"status":"resolved",
    "read":{"ok":true,"value":{"id":"good","name":"Good"}}}}
```

**Why it happened:** same RxJS rule as Experiment 3. The plain `toObservable + switchMap + toSignal` pipeline errored, so it is over. `rxResource` treats every `params` value as a brand new request, so it just recovers.

A retry button works too:

```text
[EXP] err-reload-after-error :: {"errored":{"status":"error","isLoading":false},
  "duringRetry":{"status":"reloading","isLoading":true},
  "after":{"status":"resolved","value":{"id":"x","name":"X"},"error":null}}
```

One thing to notice: `reload()` after a failure goes to `'reloading'`, not `'loading'`, even though there was no old value to preserve. So if your spinner is keyed on `status() === 'loading'`, your retry button will have no spinner. **Key it on `isLoading()`, which covers both.**

---

## Chapter 4: Refreshing — the button and the interval

Everything so far was about getting data *once*. Real screens have a refresh button, and plenty of them poll on a timer. This is where the gap widens further, because `rxResource` has an actual API for it and `toSignal` has an empty space where that API would go.

A note on the log lines in this chapter: I made `undefined` print as the string `"<undefined>"`. Inside an *array*, `JSON.stringify` does not drop `undefined` the way it does for object keys — it silently prints `null` instead, which is a completely different thing. So the marker is there to keep those two apart.

### The refresh button, with rxResource

There is a method for it. That is the whole answer:

```typescript
export class UserCard {
  userResource = rxResource({
    params: () => this.userId(),
    stream: ({ params }) => this.http.get<User>(`/api/users/${params}`),
  });

  refresh() {
    this.userResource.reload();
  }
}
```

```text
[REF] button-rxResource :: {"loaded":{"status":"resolved","value":{"id":"x","name":"Ada"}},
  "reloadReturned":true,
  "duringRefresh":{"status":"reloading","value":{"id":"x","name":"Ada"},"isLoading":true},
  "refetchedRequests":1,
  "after":{"status":"resolved","value":{"id":"x","name":"Ada v2"}}}
```

**Why it matters:** look at `duringRefresh`. The status is `'reloading'` and the value is **still Ada**. This is the difference between `'loading'` and `'reloading'` finally paying off — the old data stays on screen while the new data is fetched, so your card does not flash empty every time somebody hits refresh.

### The refresh button, with toSignal

`toSignal` has no `reload()`, so the trigger has to be part of the pipeline. The usual shape is a counter signal that nobody ever reads for its value:

```typescript
export class UserCard {
  private refreshTick = signal(0);

  user = toSignal(
    toObservable(this.refreshTick).pipe(
      switchMap(() => this.http.get<User>("/api/users/usr_123")),
    ),
  );

  refresh() {
    this.refreshTick.update((n) => n + 1);
  }
}
```

```text
[REF] button-toSignal :: {"loaded":{"id":"x","name":"Ada"},
  "duringRefresh":{"value":{"id":"x","name":"Ada"},"stillShowsOldValue":true},
  "refetchedRequests":1,"after":{"id":"x","name":"Ada v2"}}
```

**It works, and it does not flicker either** — `toSignal` holds the last value until a new one arrives, so `stillShowsOldValue` is `true`. Credit where it is due: on the plain refresh button, the two are a genuine tie on behaviour. `rxResource` just spells it in one word instead of five lines.

### Now add reactive parameters to the button

This is where the two designs stop resembling each other. You want both: a URL that follows `userId`, *and* a refresh button.

`rxResource` treats those as two separate axes and you do not write any code to combine them. `params` handles identity, `reload()` handles freshness:

```text
[REF] button-plus-params :: {
  "rxResource":{"reloadReturned":true,"onReload":["/api/r/a"],
    "onParamChange":["/api/r/b"],"final":{"id":"b","name":"Bob"}},
  "toSignal":{"onRefresh":["/api/s/a"],"onParamChange":["/api/s/b"],
    "final":{"id":"b","name":"Bob"}}}
```

Both refetch correctly. But look at what `toSignal` needed to get there — the two axes have to be merged into one Observable by hand:

```typescript
user = toSignal(
  combineLatest([toObservable(this.userId), toObservable(this.refreshTick)]).pipe(
    switchMap(([id]) => this.http.get<User>(`/api/users/${id}`)),
  ),
);
```

Notice `([id])` — you destructure the array and **throw the second element away**. The refresh counter's value is meaningless; it exists purely so that `combineLatest` emits again. That discarded slot is the tell that you are simulating a feature rather than using one.

### Gotcha: `reload()` refuses to run while it is busy

`reload()` returns a boolean, and almost nobody looks at it. It is telling you something:

```text
[REF] reload-while-busy :: {
  "whileLoading":  {"status":"loading",  "reloadReturned":false},
  "whenIdle":      {"status":"resolved", "reloadReturned":true},
  "whileReloading":{"status":"reloading","reloadReturned":false},
  "requestsOpenWhileLoading":1,"requestsOpenWhileReloading":1}
```

**A reload while a request is already in flight is refused, and returns `false`.** It does not queue, and it does not cancel and restart — the request already running is left alone to finish.

For a button, that is a free double-click guard. The `toSignal` version behaves in the opposite way: every tick of the counter starts a new request and `switchMap` cancels the previous one. For a button nobody notices the difference. For an interval, it decides everything.

### The interval, done wrong: a ticking `params`

The obvious way to poll with `rxResource` is to put a counter in `params` and bump it on a timer. Do not do this:

```typescript
private tick = signal(0);
data = rxResource({
  params: () => this.tick(),          // <- the trap
  stream: () => this.http.get<Row[]>("/api/rows"),
});
```

```text
[REF] poll-rxResource-params :: {
  "statusDuringEachTick":["loading","loading","loading"],
  "valueDuringEachTick":["<undefined>","<undefined>","<undefined>"],
  "final":{"id":"x","name":"v4"}}
```

**Why it failed:** a new `params` value means "this is a different request now", and the old value belongs to the old request. So the resource does the correct thing and throws it away — status `'loading'`, value `undefined`. Every single tick.

On screen that is a dashboard that blanks itself every five seconds. The data is right; the experience is terrible.

### The interval, done right: `reload()` on a timer

```typescript
constructor() {
  const id = setInterval(() => this.data.reload(), 5000);
  inject(DestroyRef).onDestroy(() => clearInterval(id));
}
```

```text
[REF] poll-rxResource-reload :: {
  "statusDuringEachTick":["reloading","reloading","reloading"],
  "valueDuringEachTick":[{"id":"x","name":"v1"},{"id":"x","name":"v2"},
                         {"id":"x","name":"v3"}],
  "final":{"id":"x","name":"v4"}}
```

Status `'reloading'`, and the previous version is on screen the whole time. **The rule is: `params` is for "which thing", `reload()` is for "again".** Polling is always "again".

### The interval, with toSignal

`timer` is already an Observable, so this one is genuinely elegant:

```typescript
data = toSignal(
  timer(0, 5000).pipe(switchMap(() => this.http.get<Row[]>("/api/rows"))),
);
```

```text
[REF] poll-toSignal-timer :: {"totalRequests":3,"cancelledRequests":1,
  "valueAtStartOfEachTick":["<undefined>","<undefined>",{"id":"x","name":"v2"}],
  "final":{"id":"x","name":"vLast"}}
```

Three lines, no `DestroyRef`, no `clearInterval` — when the component dies, `toSignal` unsubscribes and the timer goes with it. It does not flicker either.

But note `cancelledRequests: 1`. That is `switchMap` doing its job: a tick arrived while a request was still open, so it killed it and started a fresh one.

### What happens when the server is slower than your interval

Those two cancellation policies sound like a detail. Put both pollers on a one-second timer against a server that never answers, and it stops being a detail:

```text
[REF] starvation :: {
  "toSignal":  {"totalRequestsIssued":5,"cancelled":4,"stillAlive":1},
  "rxResource":{"totalRequestsIssued":1,"cancelled":0,"stillAlive":1,
                "extraReloadsRefused":[false,false,false,false]}}
```

**`toSignal` issued five requests and cancelled four of them.** Every tick it threw away the in-flight request and started over, so it never got far enough to deliver anything. If your endpoint is reliably slower than your poll interval, that poller can starve indefinitely while generating constant traffic.

**`rxResource` issued one request.** All four extra reloads returned `false` and were refused, leaving the original request alone to finish.

Neither is universally right. `switchMap` is correct when you want the freshest possible answer and stale in-flight work is worthless. `reload()`'s policy is correct when you want the answer to *arrive*. But you should know which one you picked, and one of them you picked by accident.

### And when one poll fails

Same RxJS rule as Experiment 3, except now it runs on a timer, which makes it much worse:

```text
[REF] poll-after-failure :: {
  "toSignal":  {"requestsAfterFailure":0,
    "read":{"ok":false,"threw":"HttpErrorResponse",
      "message":"Http failure response for /api/s/x: 500 e"}},
  "rxResource":{"requestsAfterFailure":1,"status":"reloading","read":{"ok":true}}}
```

**One 500 and the `toSignal` poller is finished. Permanently. `requestsAfterFailure: 0`.**

The error travelled up out of the `switchMap` into the `timer`, and terminated the whole pipeline. The timer is gone. Your dashboard now displays data that is frozen at the moment of the blip, with no spinner, no error, and no network traffic — and it will still be showing it tomorrow.

`rxResource` polled straight through it and recovered on the next tick.

If you take the `toSignal` route for anything that polls, `catchError` **inside** the `switchMap` is not optional. It is the difference between a transient blip and a dead screen.

### Cleanup, which is the one place toSignal wins

Destroy the component and count what keeps firing:

```text
[REF] poller-after-destroy :: {"toSignalRequestsAfterDestroy":0,
  "rxResourceRequestsAfterDestroy":0,"reloadThrew":null,
  "rxResourceStatusAfterDestroy":"idle"}
```

Both stop making requests, and pleasantly, `reload()` on a destroyed resource does not throw — the resource goes to `'idle'` and quietly ignores you.

But that is only half the story. `toSignal` cleaned itself up **because the timer was inside the Observable**. The `rxResource` version stopped issuing requests only because the resource itself was destroyed; the `setInterval` is still running, still firing every five seconds, still holding a reference to your dead component, calling a method that now does nothing.

**`rxResource` will not leak your requests, but it cannot clean up a timer it never knew about.** That `DestroyRef.onDestroy(() => clearInterval(id))` line in the example above is not decoration.

### Refresh, summarised

| | `toSignal` | `rxResource` |
| --- | --- | --- |
| Refresh button | counter signal + `switchMap` | `reload()` |
| Button **and** reactive params | `combineLatest`, discard one slot | two independent axes, no glue |
| Repeat click while busy | cancels and restarts | refused, returns `false` |
| Flicker on refresh | none | none, **if** you use `reload()` |
| Polling | `timer(0, n)` + `switchMap`, 3 lines | `setInterval` + `reload()`, plus cleanup |
| Polling via a ticking param | n/a | **blanks the screen every tick** |
| Server slower than interval | starves, cancels every attempt | one request, extra reloads refused |
| One failed poll | polling stops forever | keeps polling, recovers |
| Timer cleanup | automatic | yours to `clearInterval` |

---

## Chapter 5: So are they the same thing?

No. They are not two styles of doing one job. They do two different jobs, and only one of them is "fetch data from a server".

| | `toSignal` | `rxResource` |
| --- | --- | --- |
| Input | an Observable you already have | a description of a request |
| Reacts to signals | only via `toObservable` + `switchMap` | built in, via `params` |
| Loading state | none — `undefined` means three things | `status()`, `isLoading()`, `hasValue()` |
| On error | stores it, throws it at the next reader | captures it in `error()`, flips `status()` |
| After an error | pipeline is dead, no refetch ever | new `params` or `reload()` refetches |
| Refresh button | counter signal + `switchMap` | `reload()` |
| Polling | `timer` + `switchMap`, dies on first failure | `reload()` on a timer, survives failures |
| Lines for full error handling | ~15, and placement matters | ~4 |
| Stable since | Angular 20 | Angular 22 |

The honest counter-argument is that Experiment 5 works. You *can* get every resource behaviour out of `toSignal` — a discriminated union, `catchError` mapped into an error branch, `startWith` for loading. It recovers properly and it displays properly.

But look at what that took: fifteen lines, a hand-written type, and a `catchError` that permanently breaks the feature if you indent it wrong. That is not a style preference. **That is re-implementing `rxResource` by hand, badly, in every component.**

So the rule I use:

- **`rxResource` when you are fetching.** Anything with reactive parameters, anything that can fail, anything that needs a spinner, a retry button, or a poll. That is most data loading in most apps.
- **`toSignal` when you are adapting** something that already exists and does not fail: a `BehaviorSubject` in a service, router params, a third-party library's Observable. Add `requireSync: true` when the source always has a value — you get `Signal<T>` with no `undefined` in the type, which `rxResource` cannot give you at all.
- **If you find yourself building a `{ loading, value, error }` union around a `toSignal`, stop.** You have arrived at `rxResource` the long way round.

There is one case where `toSignal` genuinely wins and it is worth saying plainly: a source that always has a current value. `toSignal(store$, { requireSync: true })` is synchronous, `undefined`-free, and one line. `rxResource` always passes through `'loading'` first, and `defaultValue` only papers over it.

---

## TL;DR

- **Check your Angular version first.** `rxResource` used `request`/`loader` in v19 and `params`/`stream` from v20. `toSignal` lost its `rejectErrors` option in v20 and never got a replacement.
- **`toSignal` models a value. `rxResource` models a request.** Requests can be pending, fail, and be retried. Values cannot.
- **A bare `toSignal` never refetches.** Reading a signal while building a URL is not reactivity.
- **`toSignal` re-throws the error at whoever reads the signal next** — which is your template, during change detection. There is no safe question to ask it.
- **In RxJS, an Observable that errors is finished.** Put `catchError` *inside* your `switchMap` or the whole pipeline dies and never refetches again.
- **Never `catchError(() => of(fallback))` in an `rxResource` stream.** The resource reports `'resolved'` and `hasValue()` returns `true` — for `null`.
- **Never `catchError(() => EMPTY)` either.** You get Angular's NG0991 instead of your server's actual error.
- **Let the error escape the stream.** That is the entire fix. `rxResource` captures it into `error()` with the status code and response body intact.
- **Use `tap({ error })` to log.** It watches without consuming, and it is the right answer for both libraries.
- **Nothing reaches the global `ErrorHandler`.** Measured zero calls in every failing case, both libraries. If you do not log it, nobody does.
- **Guard with `hasValue()`.** In the error state `value()` throws, whatever the status docs claim.
- **`HttpErrorResponse` is not an `instanceof Error`**, and it only arrives unwrapped from Angular **21.0.4** onward. Below that, look in `.cause`.
- **Key spinners on `isLoading()`**, not `status() === 'loading'` — a retry after a failure reports `'reloading'`.
- **Refresh is `reload()`, not a ticking `params`.** A new `params` value blanks the screen on every tick; `reload()` keeps the old data visible while the new arrives.
- **`reload()` returns `false` while a request is in flight** and does nothing. Free double-click guard on a button; the reason a poller cannot starve itself.
- **A `timer + switchMap` poller cancels its own in-flight request on every tick.** Measured five requests and four cancellations against a slow server, with nothing delivered.
- **One failed poll kills a `toSignal` poller forever.** The dashboard freezes on stale data with no spinner and no error. `catchError` inside the `switchMap` is mandatory for anything on a timer.
- **`toSignal` cleans up its own timer; `rxResource` cannot clean up yours.** Pair `setInterval` with `DestroyRef.onDestroy(() => clearInterval(id))`.

---

## Resources

Documentation:

- [rxResource API reference](https://angular.dev/api/core/rxjs-interop/rxResource)
- [toSignal API reference](https://angular.dev/api/core/rxjs-interop/toSignal)
- [toObservable API reference](https://angular.dev/api/core/rxjs-interop/toObservable)
- [Async reactivity with resources](https://angular.dev/guide/signals/resource)
- [ResourceStatus API reference](https://angular.dev/api/core/ResourceStatus) — the page that says `value()` is `undefined` in the error state
- [ResourceRef API reference](https://angular.dev/api/core/ResourceRef) — `reload()`, `set()`, `hasValue()`
- [HttpErrorResponse API reference](https://angular.dev/api/common/http/HttpErrorResponse)
- [DestroyRef API reference](https://angular.dev/api/core/DestroyRef) — for cleaning up the polling timer
- RxJS: [`catchError`](https://rxjs.dev/api/operators/catchError), [`tap`](https://rxjs.dev/api/operators/tap), [`switchMap`](https://rxjs.dev/api/operators/switchMap), [`timer`](https://rxjs.dev/api/index/function/timer), [`combineLatest`](https://rxjs.dev/api/index/function/combineLatest)
- [Angular CHANGELOG](https://github.com/angular/angular/blob/main/CHANGELOG.md)

Read directly from npm packages, because the release notes did not cover it:

- `@angular/core@{16.0.0 … 22.1.0}` → `rxjs-interop/index.d.ts` and `types/rxjs-interop.d.ts`, for the `ToSignalOptions` and `RxResourceOptions` history and the `@developerPreview` / `@experimental` / `@publicApi` tags
- `@angular/core@{19.0.0, 19.2.0}` → `index.d.ts`, for the numeric `ResourceStatus` enum and `error: Signal<unknown>`
- `@angular/core@22.1.3` → `types/_api-chunk.d.ts`, for the string-union `ResourceStatus` and `error: Signal<Error | undefined>`
- `@angular/core@{21.0.3, 21.0.4}` → `fesm2022/_resource-chunk.mjs`, for `encapsulateResourceError` and the `isErrorLike` shape check

Lab: Angular 22.1.3, TypeScript 6.0.3, RxJS 7.8.2, Vitest 4.1.11, `provideHttpClientTesting`, zoneless.
