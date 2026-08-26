---
# SEO Target Queries:
#   Google: "angular linkedsignal vs computed", "angular linkedsignal vs effect", "angular linkedsignal vs model"
#   Bing:   "angular linked signal", "linked signal angular 19", "how to use signal in angular"
tags: ["typescript", "angular", "signals", "linkedsignal", "reactivity"]
categories: ["typescript", "angular"]
title: "Stop Abusing Effects: Why linkedSignal is What You Actually Wanted"
published: false
---

Be honest: how many times have you written something like this in Angular over the last two years?

```typescript
// 🙈 The code we all wrote when signals first arrived
selectedItem = signal<Item | null>(null);

constructor() {
  effect(() => {
    const items = this.items();
    untracked(() => {
      // "When items change, reset the selection to the first one!"
      this.selectedItem.set(items[0] ?? null);
    });
  });
}
```

We all did it. We needed a piece of state that defaults based on another signal, but *can also be manually overridden* when the user clicks an item in the UI.

`computed()` couldn't do it because `computed` is strictly read-only. Calling `.set()` on a computed signal is a compilation error.

So we reached for `effect()`. Then we added `allowSignalWrites: true` or wrapped things in `untracked()`. Then we saw intermittent `ExpressionChangedAfterItHasBeenCheckedError` exceptions in tests, timing issues during hydration, and circular dependency bugs.

Angular finally gave us the real solution: **`linkedSignal`**.

Here is why it changes everything, and how to use the advanced computation pattern nobody talks about.

## The Mental Model

Think of `linkedSignal` as a **writable signal that has a reset trigger**.

```typescript
import { Component, input, linkedSignal } from '@angular/core';

@Component({
  selector: 'app-item-selector',
  template: `
    <ul>
      @for (item of items(); track item.id) {
        <li
          [class.active]="item.id === selected()?.id"
          (click)="selected.set(item)"
        >
          {{ item.name }}
        </li>
      }
    </ul>
  `
})
export class ItemSelectorComponent {
  items = input.required<Item[]>();

  // ✅ Automatically initializes or resets to items()[0] whenever items() changes,
  // but allows .set() or .update() when the user clicks!
  selected = linkedSignal(() => this.items()[0] ?? null);
}
```

Look at how concise that is. No `effect()`, no `untracked()`, no constructor boilerplate, no lifecycle hooks.

When `items()` emits a new array from the parent component, `selected` resets to `items()[0]`. When the user clicks an item in the list, `selected.set(item)` updates the signal immediately.

## The Big Problem: Dropping User State

The simple syntax `linkedSignal(() => this.items()[0])` is great for simple cases, but consider a real-world scenario:

1. The user selects **Item #3** from a list of 10 items.
2. An async background refresh happens, adding a new item to the top of the list.
3. Because `items()` updated, the naive `linkedSignal` resets to the first item, **wiping out the user's active selection**!

That is terrible UX. What you *actually* want is:

> *"If the items list updates, keep my current selection IF it is still in the new list. Only reset to the default if my selected item was deleted."*

Prior to `linkedSignal`, writing that logic required dozens of lines of defensive RxJS or nasty effect hacks.

With `linkedSignal`, it is built directly into the API through the **`previous`** parameter.

## The Pro Pattern: Using `source` and `computation`

Instead of passing a simple factory function, you can pass an options object with `source` and `computation`:

```typescript
import { Component, input, linkedSignal } from '@angular/core';

interface ProductVariant {
  id: string;
  name: string;
  inStock: boolean;
}

@Component({
  selector: 'app-variant-picker',
  template: `
    <div class="variants">
      @for (v of variants(); track v.id) {
        <button
          [class.selected]="v.id === selectedVariant()?.id"
          (click)="selectedVariant.set(v)"
        >
          {{ v.name }}
        </button>
      }
    </div>
  `
})
export class VariantPickerComponent {
  variants = input.required<ProductVariant[]>();

  selectedVariant = linkedSignal<ProductVariant[], ProductVariant | null>({
    source: this.variants,
    computation: (newVariants, previous) => {
      // previous.value: The value of selectedVariant right before this re-computation!
      // previous.source: The previous array of variants!

      if (!previous?.value) {
        return newVariants[0] ?? null;
      }

      // Check if the user's previously chosen variant still exists in the new list:
      const stillExists = newVariants.find(v => v.id === previous.value?.id);

      // Keep it if found; otherwise, fallback to first available
      return stillExists ?? newVariants[0] ?? null;
    }
  });
}
```

Notice what just happened:
* `previous.value` lets you inspect what the user had selected *before* the input changed.
* You make an intelligent decision: keep their selection if valid, or gracefully fall back.
* Everything remains synchronous, reactive, and glitched-free.

## Quick Cheat Sheet: Which Signal Should You Use?

| Scenario | Use |
| :--- | :--- |
| Pure derived data (e.g. `fullName = first + ' ' + last`) | `computed()` |
| Read-only async HTTP data from server | `resource()` / `rxResource()` |
| State that user can modify, but resets when an input changes | `linkedSignal()` |
| Logging to analytics, talking to non-reactive 3rd party DOM canvas | `effect()` |

If you catch yourself typing `untracked()` inside an `effect()` to set another signal, stop. Delete the effect, and replace it with `linkedSignal`.
