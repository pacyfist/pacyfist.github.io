---
tags: ["typescript", "angular", "vitest", "karma", "testing"]
categories: ["typescript", "angular"]
title: "Angular Karma to Vitest Migration: The Missing Import"
image:
  path: /assets/img/2026-08-18/main.jpg
  alt: A robot that migrated zero projects, reporting complete success.
---

Angular ships an official migration that moves your unit tests from Karma to Vitest. So you upgrade to Angular 22, run it, and you are done. Right?

Here is what it printed for my project:

```text
--- Karma to Vitest Migration Summary ---
Projects migrated: 0
Projects skipped (non-applications): 0
Projects skipped (missing application builder): 0
-----------------------------------------

Migration completed (No changes made).
```

Zero migrated. Zero skipped, for any reason it bothered to name. No error, no warning, nothing to search for. Just a summary full of zeroes and a cheerful "Migration completed".

It took me a while to work out why, and then a while longer to get the tests green by hand. Both halves are worth writing down.

## The setup

I built a small Angular 21 app with Karma and Jasmine, then upgraded it to Angular 22. One component: a product search box with a 300ms debounce, an injected service, a computed filter, and an output event. Nine tests covering the logic, plus the two the CLI generates.

Eleven green on Karma, before touching anything:

```bash
npx ng test --watch=false
```

```text
Chrome 151.0.0.0 (Linux 0.0.0): Executed 11 of 11 SUCCESS (0.164 secs / 0.137 secs)
TOTAL: 11 SUCCESS
```

Then the upgrade, which goes fine and ends by offering the migration:

```bash
npx ng update @angular/core@22 @angular/cli@22
```

```text
** Optional migrations of package '@angular/cli' **

This package has 2 optional migrations that can be executed.
❯ Migrate projects using legacy Karma unit-test builder to the new unit-test builder with Vitest.
  ng update @angular/cli --name migrate-karma-to-vitest
```

Read that description again, because the answer is hiding in it. **"legacy Karma unit-test builder."**

## Why the migration skips you

The migration only recognises two builders, and if yours is neither, it moves on without a word. I went and read it, in `node_modules/@schematics/angular/migrations/migrate-karma-to-vitest/migration.js`:

```js
switch (testTarget.builder) {
  case workspace_models_1.Builders.Karma:
    isKarma = true;
    needDevkitPlugin = true;
    break;
  case workspace_models_1.Builders.BuildKarma:
    isKarma = true;
    break;
}
if (!isKarma) {
  continue;
}
```

Those two are the old `@angular-devkit/build-angular:karma` and `@angular/build:karma`. Now look at what Angular 21 actually gave me:

```bash
npx ng config projects.shop.architect.test
```

```text
{
  "builder": "@angular/build:unit-test",
  "options": {
    "runner": "karma"
  }
}
```

`@angular/build:unit-test`. Not either of them.

Angular 21 already moved everyone to one unified test builder, where Karma is just a `runner` setting. So the migration written to rescue old projects looks at a modern one, matches nothing, and hits that `continue`. It is not even counted as skipped, which is why every number in the summary was zero.

**If your project started on Angular 21 or later, the automated migration will never do anything for you.** It is for people coming from Angular 20 and earlier. Nothing in the output says so.

The good news: what it would have done for you is four small changes.

## Change 1: flip the runner

The whole builder swap is one word in `angular.json`:

```json
"test": {
  "builder": "@angular/build:unit-test",
  "options": {
    "runner": "vitest"
  }
}
```

Run the tests and Angular tells you exactly what is missing:

```bash
npx ng test --watch=false
```

```text
The following packages are required but were not found:
  - vitest
  - A DOM environment is required for non-browser tests. Please install either "jsdom" or "happy-dom".
Please install the missing packages and rerun the test command.
```

That is a genuinely good error message. Do what it says:

```bash
npm install -D vitest jsdom
```

```text
added 64 packages, and audited 536 packages in 6s

found 0 vulnerabilities
```

## Change 2: the Jasmine words have to go

Now the tests actually run, and nine of eleven fail with the same line:

```text
ReferenceError: jasmine is not defined
 ❯ src/app/product-search.spec.ts:19:5
    17|
    18|   beforeEach(async () => {
    19|     service = jasmine.createSpyObj<ProductService>('ProductService', […
      |     ^
```

Two things worth noticing here. The CLI-generated `app.spec.ts` passed without a single edit. And `describe`, `it`, `expect` and `beforeEach` all still work, because Vitest provides them as globals. **Only the words starting with `jasmine.` broke.**

Here is the whole translation table for my component's tests:

| Jasmine                              | Vitest                                |
| ------------------------------------ | ------------------------------------- |
| `jasmine.createSpyObj('S', ['m'])`   | `{ m: vi.fn() }`                      |
| `spy.and.returnValue(x)`             | `spy.mockReturnValue(x)`              |
| `jasmine.SpyObj<T>` (the type)       | `{ m: ReturnType<typeof vi.fn> }`     |
| `toBeTrue()` / `toBeFalse()`         | `toBe(true)` / `toBe(false)`          |
| `toHaveBeenCalledOnceWith(x)`        | `toHaveBeenCalledExactlyOnceWith(x)`  |
| `jasmine.objectContaining(x)`        | `expect.objectContaining(x)`          |

So the spy setup goes from this:

```ts
service = jasmine.createSpyObj<ProductService>('ProductService', ['search']);
service.search.and.returnValue(of(PRODUCTS));
```

to this:

```ts
service = { search: vi.fn() };
service.search.mockReturnValue(of(PRODUCTS));
```

`vi` is a global, so there is nothing to import. But TypeScript needs telling, in `tsconfig.spec.json`:

```json
"types": ["vitest/globals"]
```

Everything else in these tests survived untouched: `TestBed`, `ComponentFixture`, `fixture.detectChanges()`, `toEqual`, `toContain`, `not.toHaveBeenCalled()`, and poking at `fixture.nativeElement`.

## Change 3: the import nobody mentions

Nine failures down to seven. All seven are the same, and they are all my `fakeAsync` tests:

```text
Error: Expected to be running in 'ProxyZone', but it was not found.
 ❯ _ProxyZoneSpec.assertPresent node_modules/zone.js/fesm2015/zone-testing.js:882:13
 ❯ fakeAsyncFn node_modules/zone.js/fesm2015/zone-testing.js:1647:42
```

`fakeAsync` is the helper that lets you fast-forward time instead of waiting for it. My debounce test calls `tick(299)`, checks nothing happened, then `tick(1)` and checks the search fired. Under Karma this worked. Under Vitest it cannot find the zone it needs to run in.

So you add a setup file that loads zone testing, and point the builder at it:

```ts
import 'zone.js';
import 'zone.js/testing';
```

```json
"options": {
  "runner": "vitest",
  "setupFiles": ["src/test-setup.ts"]
}
```

And it fails in exactly the same way. Still seven, still `ProxyZone`.

Here is the bit that cost me the most time. **`zone.js/testing` patches Jasmine and Mocha. It does not patch Vitest.** It hooks into the test framework's own `it` and `beforeEach` to wrap each test in a zone, and it has never heard of Vitest's.

zone.js ships the Vitest hook separately:

```bash
ls node_modules/zone.js/fesm2015/ | grep patch
```

```text
jasmine-patch.js
mocha-patch.js
vitest-patch.js
```

There it is, sitting next to its siblings, not included in the bundle you just imported. One more line in the setup file:

```ts
import 'zone.js';
import 'zone.js/testing';
import 'zone.js/plugins/vitest-patch';
```

```text
 Test Files  2 passed (2)
      Tests  11 passed (11)
```

Eleven green, same as Karma. That single import took the suite from seven failures to zero.

## Change 4: the trap that reports success

One of my tests used the old callback style, where you get a `done` function and call it when the async work finishes:

```ts
it('emits the selected product', (done) => {
  component.selected.subscribe((p) => {
    expect(p).toEqual(jasmine.objectContaining({ id: 3, name: 'Monitor' }));
    done();
  });
  component.select(PRODUCTS[2]);
});
```

Vitest does not support `done`. What makes this nasty is **how** it does not support it. The test itself reports green. Then, separately, at the bottom of the run:

```text
⎯⎯⎯⎯⎯⎯ Unhandled Errors ⎯⎯⎯⎯⎯⎯

Error: done() callback is deprecated, use promise instead
```

A passing test and a failing suite, described in two places that are nowhere near each other. In a suite of ten tests you will spot it. In a suite of eight hundred, good luck.

Return a promise instead:

```ts
it('emits the selected product', () => {
  return new Promise<void>((resolve) => {
    component.selected.subscribe((p) => {
      expect(p).toEqual(expect.objectContaining({ id: 3, name: 'Monitor' }));
      resolve();
    });
    component.select(PRODUCTS[2]);
  });
});
```

## The finished config

Four files. That is the entire migration:

```text
angular.json        runner: karma -> vitest, plus setupFiles
src/test-setup.ts   new, three imports
tsconfig.spec.json  types: jasmine -> vitest/globals, and include the setup file
package.json        add vitest + jsdom, remove karma and jasmine
```

That last one is satisfying:

```bash
npm uninstall karma karma-chrome-launcher karma-coverage karma-jasmine karma-jasmine-html-reporter jasmine-core @types/jasmine
```

```text
removed 123 packages, and audited 413 packages in 1s

found 0 vulnerabilities
```

One thing to sweep up afterwards. The Angular 22 update adds a package called `istanbul-lib-instrument` **"if Karma unit testing is used"**. Once Karma is gone, so is the reason for it. It will sit in your `package.json` forever if you do not look.

Also add the setup file to `include` in `tsconfig.spec.json`, or the build nags at you:

```text
▲ [WARNING] File 'src/test-setup.ts' not found in TypeScript compilation. [plugin angular-compiler]
```

## The benchmark section, which you should ignore

Every migration post is legally required to include a speed comparison, so here is mine. Eleven tests. One laptop. A stopwatch made of `$SECONDS`.

```text
Karma:   7s, 5s, 5s
Vitest:  5s, 4s, 5s
```

There you go. Vitest is one second faster, plus or minus one second.

Please do not put that in a slide deck. Eleven tests is not a benchmark, it is a rounding error with ambitions. Most of those seconds are Angular building the app, which happens either way and does not care which runner comes next.

Migrate because Karma is gone from new projects, not because of my stopwatch.

## If you are already zoneless, most of this vanishes

A footnote that is really a headline for some of you.

My first attempt at building the Angular 21 baseline used plain `ng new` defaults, and every `fakeAsync` test failed before I had migrated anything at all:

```text
Error: zone-testing.js is needed for the fakeAsync() test helper but could not be found.
        Please make sure that your environment includes zone.js/testing
```

Angular 21 made zoneless the default, so a genuinely new project has no zone.js. I had to scaffold with `--zoneless false` to model a real app carrying an older Jasmine suite.

If your app is already zoneless, you have no `fakeAsync` to rescue, which means Change 3 does not apply to you at all. Your migration is the runner flag, the package swap, and some search and replace.

## Summary

- **The official `migrate-karma-to-vitest` does nothing for projects created on Angular 21 or later.** It only matches the two legacy Karma builders, and reports zero migrated and zero skipped.
- Doing it by hand is four changes: the `runner` value, a setup file, `tsconfig.spec.json` types, and the packages.
- Vitest gives you `describe`, `it`, `expect` and `vi` as globals. **Only `jasmine.*` calls need rewriting**, and the generated `app.spec.ts` needs nothing.
- `fakeAsync` needs **`zone.js/plugins/vitest-patch`**. `zone.js/testing` alone is not enough, because it patches Jasmine and Mocha only.
- `done()` callbacks report a **green test and a failing suite**. Return a promise.
- Delete `istanbul-lib-instrument` once Karma is gone.
- My benchmark says Vitest is one second faster, and my benchmark is eleven tests and a stopwatch. **Migrate for the tooling, not the stopwatch.**

Closing tip: before you start, get your suite green on Karma under Angular 22 first, and commit. Then every failure you see afterwards belongs to the migration and nothing else, which turns a scary refactor into a list you can tick off.
