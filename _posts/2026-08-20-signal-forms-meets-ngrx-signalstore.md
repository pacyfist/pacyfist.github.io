---
# SEO Target Queries:
#   Google: "angular signal store best practices", "angular signal store vs ngrx", "angular signal store example"
#   Bing:   "angular signal store and signal forms", "signal store angular"
tags: ["typescript", "angular", "signal forms", "ngrx", "signalstore"]
categories: ["typescript", "angular"]
title: "Signal Forms Meets SignalStore: The Architecture You Actually Need"
published: false
---

A few days ago, I wrote about [Angular Signal Forms](https://www.pacyfist.dev/posts/angular-signal-forms-14-awkward-questions-and-one-nasty-surprise/) and how they eliminate the clunky `FormGroup` ceremony we've endured for years.

Almost immediately, people asked the logical next question:

> *"How does this play with NgRx SignalStore? Can I bind a Signal Form directly to a SignalStore, or do they fight each other?"*

They fight each other—unless you respect where the boundaries lie.

Let's look at why naive integrations crash into wall after wall, and the clean architecture that actually works in production.

## The Clash of Philosophies

Before writing a single line of code, consider the fundamental design difference between the two tools:

1. **NgRx SignalStore** is strictly **unidirectional and immutable**. Its state properties are read-only signals. To mutate state, you must dispatch changes through `patchState(store, ...)` or custom store methods.
2. **Forms** are inherently **interactive, local, and transient**. While the user is typing `"fili"`, `"filip"`, backspacing, and fixing typos, the form state is in flux, invalid, dirty, or untouched.

If you try to make your global or feature SignalStore directly mirror every keystroke of an active form control, you hit problems immediately.

### Bad Idea #1: Mutating a Store Signal Directly

SignalStore exposes state slices as read-only signals:

```typescript
export const UserStore = signalStore(
  withState({
    user: { name: 'Filip', email: 'filip@example.com' }
  })
);
```

In your component, you might be tempted to do:

```typescript
// ❌ FAILS: userStore.user is a Signal, not a WritableSignal!
name = userStore.user.name;
```

You can't pass a read-only signal into a two-way binding or form control expecting it to mutate. It won't compile.

### Bad Idea #2: The Infinite Sync Loop

Then comes the "clever" idea: let's create a local form and sync both ways with an `effect()`!

```typescript
// ⚠️ THE FEEDBACK LOOP TRAP
effect(() => {
  // When store changes, update form
  const currentUser = this.store.user();
  untracked(() => this.form.reset(currentUser));
});

// And when form changes, update store:
this.form.valueChanges.subscribe(val => {
  this.store.updateUser(val); // This triggers the store signal, which triggers the effect!
});
```

Congratulations: you've built an infinite feedback loop. Even with `distinctUntilChanged()`, handling validation errors, dirty state resets, and cancellation during rapid typing will make your hair turn grey.

## Pattern 1: The Load-and-Submit Boundary (Recommended)

In 90% of web apps, the store should not care about every character typed into an `<input>`. The store cares about **saved entities** and **async orchestration**.

Keep the form state local to the component, initialize it once from the store, and submit atomically:

```typescript
import { Component, inject, OnInit } from '@angular/core';
import { UserStore } from './user.store';

@Component({
  selector: 'app-user-settings',
  template: `
    <form (ngSubmit)="onSubmit()">
      <div>
        <label>Name</label>
        <input [formControl]="form.controls.name" />
      </div>

      <div>
        <label>Email</label>
        <input [formControl]="form.controls.email" />
      </div>

      <button type="submit" [disabled]="store.isSaving() || form.invalid">
        {{ store.isSaving() ? 'Saving...' : 'Save Changes' }}
      </button>
    </form>
  `
})
export class UserSettingsComponent implements OnInit {
  readonly store = inject(UserStore);

  // Local form definition
  form = new FormGroup({
    name: new FormControl('', { nonNullable: true }),
    email: new FormControl('', { nonNullable: true }),
  });

  ngOnInit() {
    // Populate form with current store state
    const user = this.store.user();
    if (user) {
      this.form.patchValue(user);
    }
  }

  onSubmit() {
    if (this.form.valid) {
      this.store.saveProfile(this.form.getRawValue());
    }
  }
}
```

The component owns form lifecycle and validation. The SignalStore owns HTTP calls, loading indicators, and error banners. Clean, decoupled, zero loops.

## Pattern 2: Auto-Saving with rxMethod and Debounce

What if your product requirement genuinely *demands* continuous auto-saving (like Google Docs or Notion settings)?

This is where NgRx SignalStore's `rxMethod` shines. Instead of pushing updates inside an `effect`, you stream form events through a debounced store method:

```typescript
import { signalStore, withState, withMethods, patchState } from '@ngrx/signals';
import { rxMethod } from '@ngrx/signals/rxjs-interop';
import { pipe, switchMap, debounceTime, distinctUntilChanged, tap } from 'rxjs';
import { tapResponse } from '@ngrx/operators';
import { inject } from '@angular/core';
import { UserService, UserProfile } from './user.service';

export const UserSettingsStore = signalStore(
  withState({
    user: null as UserProfile | null,
    isSaving: false,
    lastSaved: null as Date | null,
  }),
  withMethods((store, userService = inject(UserService)) => ({
    autoSaveProfile: rxMethod<Partial<UserProfile>>(
      pipe(
        debounceTime(500),
        distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr)),
        tap(() => patchState(store, { isSaving: true })),
        switchMap((changes) =>
          userService.update(changes).pipe(
            tapResponse({
              next: (updated) => patchState(store, {
                user: updated,
                isSaving: false,
                lastSaved: new Date()
              }),
              error: (err) => {
                console.error(err);
                patchState(store, { isSaving: false });
              }
            })
          )
        )
      )
    )
  }))
);
```

In your component, wire the form's value stream directly into the `rxMethod`:

```typescript
export class UserSettingsComponent implements OnInit {
  readonly store = inject(UserSettingsStore);
  form = new FormGroup({ ... });

  ngOnInit() {
    // Stream form updates cleanly into the store method
    this.store.autoSaveProfile(this.form.valueChanges);
  }
}
```

Because `rxMethod` handles observable teardown and unsubscription upon component destruction automatically, there is no subscription leak.

## Summary

When pairing forms with NgRx SignalStore:
1. **Don't force forms to bind two-way into read-only store signals.**
2. **Keep user typing local to the component form.**
3. **Use atomic method dispatches** for standard submit actions.
4. **Use `rxMethod` with `debounceTime`** when continuous auto-save is required.
