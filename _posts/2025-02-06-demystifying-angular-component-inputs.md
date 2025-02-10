---
tags: ["typescript", "angular", "components", "signals"]
categories: ["typescript", "angular"]
title: "Demystifying Angular Component Inputs: From Old School to Signal Power"
image:
  path: /assets/img/2025-02-06/angular-signals.jpg
  alt: Cartoon interpretation of Angular signals.
---

Hey there, fellow Angular nerds!

I've been knee-deep in Angular projects for quite a while now, and one thing I've noticed is that component inputs, while fundamental, often don't get used to their full potential. I couldn't find a single, clear guide covering all the different flavors of inputs you can use. Plus, I've seen developers wrangling with complex logic to handle what should be straightforward scenarios.

So, I thought, why not create that guide myself? Let's dive into the world of Angular component inputs, exploring both the classic `@Input` decorator approach and the shiny new signal-based `input<T>()`. I'll show you how to keep things simple, readable, and maintainable.

## The `@Input` Decorator: The Old Reliable

For years, the `@Input` decorator has been the go-to way to pass data into every Angular components. It's a solid, dependable tool, but let's be honest, it can get a bit verbose.

Here's a quick rundown of the different ways you can use `@Input`:

{% raw %}
```typescript
import { Component, Input } from '@angular/core';

@Component({
    selector: 'app-my-component',
    template: `
        <p>Optional Input: {{ optionalInput }}</p>
        <p>Optional Input with Default: {{ optionalInputWithDefault }}</p>
        <p>Required Input: {{ requiredInput }}</p>
        <p>Optional Transforming Input: {{ optionalTransformingInput }}</p>
        <p>Required Transforming Input: {{ requiredTransformingInput }}</p>
        `,
    standalone: true,
})
export class MyComponent {
    @Input() optionalInput?: string;
    @Input() optionalInputWithDefault: string = 'default value';
    @Input({ required: true }) requiredInput!: string;
    @Input({
        transform: (value: string) => value.toUpperCase(),
    }) optionalTransformingInput?: string;
    @Input({
        required: true,
        transform: (value: string) => value.toUpperCase(),
    }) requiredTransformingInput!: string;
}
```
{% endraw %}

Let's break this down:

* **`@Input() optionalInput?: string;`**: A standard optional input. The question mark (`?`) means the parent component doesn't *have* to provide a value. If it doesn't, this property will be `undefined`.

* **`@Input() optionalInputWithDefault: string = 'default value';`**: Another optional input, but this time with a default value. If the parent component doesn't provide a value, this property will be initialized with `'default value'`.

* **`@Input({ required: true }) requiredInput!: string;`**: This is a *required* input. The `required: true` option and the non-null assertion operator (`!`) tell Angular not to show the possible nullability warning, because the parent component *must* provide a value for this input. If it doesn't, you'll get an error.

* **`@Input({ transform: (value: string) => value.toUpperCase(), }) optionalTransformingInput: string;`**: This is where things get interesting. The `transform` option lets you modify the input value before it's used in your component. In this case, we're converting the input to uppercase. This input is optional.

* **`@Input({ required: true, transform: (value: string) => value.toUpperCase(), }) requiredTransformingInput: string;`**: The best of both worlds! This input is both required *and* transformed. The parent component *must* provide a value, and that value will be converted to uppercase.

## Signal Inputs: The Cool Kid on the Block

Now, let's talk about signal inputs. Signals are a game-changer in Angular, offering fine-grained reactivity and improved performance. Using signals for component inputs is a more modern and often cleaner approach.

Here's how the same examples look using signal inputs:

{% raw %}
```typescript
import { Component, input } from '@angular/core';

@Component({
    selector: 'app-my-component',
    template: `
        <p>Optional Input: {{ optionalInput() }}</p>
        <p>Optional Input with Default: {{ optionalInputWithDefault() }}</p>
        <p>Required Input: {{ requiredInput() }}</p>
        <p>Optional Transforming Input: {{ optionalTransformingInput() }}</p>
        <p>Required Transforming Input: {{ requiredTransformingInput() }}</p>
        `,
    standalone: true,
})
export class MyComponent {
    optionalInput = input<string>();
    optionalInputWithDefault = input<string>('default value');
    requiredInput = input.required<string>();
    optionalTransformingInput = input<string, string>('default value', {
        transform: (value: string) => value.toUpperCase(),
    });
    requiredTransformingInput = input.required<string, string>({
        transform: (value: string) => value.toUpperCase(), 
    });
}
```
{% endraw %}

Let's break this down:

* **`optionalInput = input<string>();`**: A simple optional input. If the parent component doesn't provide a value, the signal will hold `undefined`. Note that you need to call the signal `optionalInput()` to access it's value in the template.

* **`optionalInputWithDefault = input<string>('default value');`**: An optional input with a default value. If the parent doesn't provide a value, the signal will be initialized with `'default value'`.

* **`requiredInput = input.required<string>();`**: A required input. If the parent component doesn't provide a value, Angular will throw an error.

* **`optionalTransformingInput = input<string, string>('default value', { transform: (value: string) => value.toUpperCase(), });`**: An optional input with a transform function. The transform function is applied to the input value before it's stored in the signal. Note that this way of setting up signal required a default value.

* **`requiredTransformingInput = input.required<string, string>({ transform: (value: string) => value.toUpperCase(), });`**: A required input with a transform function.

## Why Signals?

You might be wondering, "Why should I switch to signal inputs?" Here's a few reasons:

* **Fine-grained Reactivity:** Signals provide more precise change detection, leading to better performance. Angular knows *exactly* what has changed and only updates the parts of the DOM that need to be updated.
* **Improved Readability:** Signal inputs can be more concise and easier to understand.
* **Type Safety:** Signals are strongly typed, which can help prevent errors.
* **They are the future:** Angular is moving more and more towards signals.

## Conclusion

Component inputs are a fundamental part of Angular development. Whether you're using the trusty `@Input` decorator or embracing the power of signal inputs, understanding the different options available will help you write cleaner, more maintainable, and more efficient code.

So, go forth and build amazing components! And remember, less is more!
