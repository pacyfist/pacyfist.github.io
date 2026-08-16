---
tags: ["typescript", "angular", "signal forms", "validation", "forms"]
categories: ["typescript", "angular"]
title: "Angular Signal Forms: 14 Awkward Questions and One Nasty Surprise"
image:
  path: /assets/img/2026-08-16/main.jpg
  alt: A form that finally validates itself, and one sneaky button.
---

I have typed `this.fb.group({ ... })` so many times that my fingers do it before my brain catches up. Saturday night they did it again, for the signup page of a weekend project that currently has exactly one user: me.

Then came the part I always forget I hate. A custom validator for "do these two passwords match", which sits on the confirm field - so it doesn't re-run when you edit the _first_ password. Which means a `valueChanges` subscription. Which means remembering to unsubscribe. For a checkbox-and-two-inputs form nobody but me will ever see.

Angular 22 made **Signal Forms** stable back in June. So I deleted all of it and rebuilt the form the new way, then spent the rest of the evening poking it with a stick - asking it awkward questions and writing down what it actually did.

Most answers delighted me. One of them would have shipped a bug. Let's go.

## Setting Up

Nothing exotic here, which is the nicest part of this post. No preview SDK, no flags:

```bash
npx @angular/cli@22 new signalforms-lab --style=scss --ssr=false --defaults
```

```text
✔ Packages installed successfully.
```

Let's confirm what we're on:

```bash
npx ng version
```

```text
Angular CLI       : 22.1.4
Angular           : 22.1.2
Node.js           : 26.5.0
Package Manager   : npm 11.17.0
Operating System  : linux x64
```

**You don't install anything extra.** `@angular/forms` is already in a default Angular project. Signal Forms just live in a different entry point:

```typescript
import { form, FormField, required, email } from '@angular/forms/signals';
```

That's it. Stable APIs, no `experimental` anything.

## The Form

Here's the shape of the data. A plain interface - no `FormGroup`, no `FormControl`:

```typescript
export interface SignupData {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  age: number;
  plan: 'free' | 'pro';
  couponCode: string;
  referralCode: string;
  team: { email: string }[];
}
```

And here's the whole form. A signal holding the data, and a schema describing the rules:

```typescript
export class Signup {
  readonly model = signal<SignupData>(emptySignup());

  readonly signupForm = form(this.model, (path) => {
    required(path.username, { message: 'Pick a username' });
    minLength(path.username, 3, { message: 'At least 3 characters' });

    required(path.email, { message: 'Email is required' });
    email(path.email, { message: 'That does not look like an email' });

    required(path.password, { message: 'Password is required' });
    minLength(path.password, 8, { message: 'At least 8 characters' });

    // Cross-field rule
    validate(path.confirmPassword, ({ value, valueOf }) =>
      value() !== valueOf(path.password)
        ? { kind: 'mismatch', message: 'Passwords do not match' }
        : null,
    );

    min(path.age, 18, { message: 'You must be 18 or older' });

    // Rules that only exist on the Pro plan
    applyWhen(
      path,
      ({ valueOf }) => valueOf(path.plan) === 'pro',
      (pro) => {
        required(pro.couponCode, { message: 'Pro needs a coupon code' });
        pattern(pro.couponCode, /^PRO-\d{4}$/, { message: 'Format: PRO-1234' });
      },
    );

    // Same rules for every row of the team array
    applyEach(path.team, (member) => {
      required(member.email, { message: 'Team member needs an email' });
      email(member.email, { message: 'Invalid team member email' });
    });
  });
}
```

## The Template

This is the part I found confusing for the first ten minutes, so let's go slowly.

There is **no `formGroup`, no `formControlName`, no wrapper directive on the `<form>`**. You bind each input straight to a field with `[formField]`:

{% raw %}

```html
<input type="email" [formField]="signupForm.email" />
```

{% endraw %}

That single binding does four jobs: reads the value, writes changes back to your signal, sets `touched` on blur, and applies `disabled`/`readonly` to the DOM element.

The bit that trips you up is the **double call**. Watch the brackets:

| You write | You get |
| --- | --- |
| `signupForm.email` | the **field** - this is what you bind to |
| `signupForm.email()` | the field's **state** object |
| `signupForm.email().value()` | the current value |
| `signupForm.email().errors()` | the errors array |
| `signupForm.email().touched()` | has it been blurred |

So `signupForm.email` goes in the binding, and `signupForm.email()` starts every read. Once that clicks, the rest is boring in the best way.

Here's one complete field - the username, which has both an async spinner and errors:

{% raw %}

```html
<label>
  Username
  <input type="text" [formField]="signupForm.username" />
</label>

@if (signupForm.username().pending()) {
  <small class="pending">checking availability…</small>
}

@if (signupForm.username().touched() && signupForm.username().invalid()) {
  <ul class="errors">
    @for (error of signupForm.username().errors(); track error.kind) {
      <li>{{ error.message }}</li>
    }
  </ul>
}
```

{% endraw %}

Every other simple field is the same three lines with a different name. A `<select>` works identically - bind it and Angular handles the rest:

{% raw %}

```html
<select [formField]="signupForm.plan">
  <option value="free">Free</option>
  <option value="pro">Pro</option>
</select>
```

{% endraw %}

The array is the one genuinely new shape. You iterate the **field** - not the model - and each item gives you a field you can bind:

{% raw %}

```html
@for (member of signupForm.team; track $index) {
  <div class="row">
    <input type="email" [formField]="member.email" />
    <button type="button" (click)="removeTeamMember($index)">remove</button>
  </div>
}
<button type="button" (click)="addTeamMember()">Add team member</button>
```

{% endraw %}

Note `member.email` - `member` is a field tree for that row, so `member.email` is a real field with its own state and errors, exactly like a top-level one.

Adding and removing rows is plain signal work. No `FormArray`:

```typescript
addTeamMember() {
  this.model.update((m) => ({ ...m, team: [...m.team, { email: '' }] }));
}

removeTeamMember(index: number) {
  this.model.update((m) => ({
    ...m,
    team: m.team.filter((_, i) => i !== index),
  }));
}
```

And the submit button reads state off the form root - note the `()` on `signupForm` itself:

{% raw %}

```html
<button type="submit" [disabled]="signupForm().submitting() || signupForm().pending()">
  {{ signupForm().submitting() ? 'Saving…' : 'Sign up' }}
</button>
```

{% endraw %}

That `pending()` in the disabled check looks like belt and braces. By the end of this post you'll know it's the braces.

Finally, the component only needs `FormField` imported - that's the directive powering every `[formField]` above:

```typescript
@Component({
  selector: 'app-signup',
  templateUrl: './signup.html',
  imports: [FormField],
})
export class Signup { /* ... */ }
```

It compiled first try:

```bash
npx ng build
```

```text
Application bundle generation complete. [4.364 seconds]
```

That includes the template type-check of `[formField]` inside an `@for` over the team array. I genuinely expected to fight that. I didn't.

## How I Tested It

Rather than click around, I wrote a spec that asks one question per test and prints the answer. Angular 22 runs **vitest** by default, headless, no browser needed:

```bash
npx ng test --no-watch --reporters verbose
```

Every output block below is real output from that run. The two places I quote Angular's type definitions instead, I say so.

Every question below started life as something I hand-wired in Reactive Forms. A `valueChanges` subscription, a `setValidators` call, a `patchValue`, an `if (form.invalid) return`. **So each test is really me asking which of my old habits are now dead code** - and one of them told me I had to add something instead.

## The Basics (These Just Work)

**Are there errors before the user has touched anything?**

Reactive Forms marks a required field invalid before the user has done anything, so `@if (field.invalid)` around your error markup means the page loads covered in red. **Whether errors exist at time zero decides how you write every error block in the template**, so I wanted to know before writing any of them.

```typescript
const username = c.signupForm.username();
console.log('  valid   :', username.valid());
console.log('  touched :', username.touched());
console.log('  errors  :', messages(username));
```

```text
  valid   : false
  touched : false
  errors  : [ 'Pick a username' ]
```

Yes. Errors exist from the very first render. So **gate your error display on `touched()`**, not on whether errors exist - otherwise your form screams at people the moment it loads.

(`messages()` is just a tiny helper I used everywhere to keep the output readable:)

```typescript
function messages(field: { errors: () => readonly { message?: string }[] }) {
  return field.errors().map((e) => e.message);
}
```

**Is the model really two-way?**

In Reactive Forms there are always two copies of the truth. The `FormGroup` holds one, my component holds the other, and I keep them in step with `patchValue` going out and a `valueChanges` subscription coming back. Signal Forms claims my signal simply **is** the form value, so I pushed on it from both ends.

Set the field, read the model:

```typescript
c.signupForm.username().value.set('bobby');
console.log('  field value :', c.signupForm.username().value());
console.log('  model value :', c.model().username);
```

```text
  field value : bobby
  model value : bobby
```

Then the other direction - set the model, read the field:

```typescript
c.model.update((m) => ({ ...m, email: 'from-model@example.com' }));
console.log('  field value :', c.signupForm.email().value());
```

```text
  field value : from-model@example.com
```

Both directions. Your signal is the single source of truth, and there's no `patchValue` ceremony.

**Does typing in an actual `<input>` do the same?**

The two tests above poked the form from TypeScript, which is not how anybody fills in a form. A `.set()` from code never goes anywhere near the `[formField]` binding. **If that binding only did half its job, every other test in this post would be measuring something users never do.** So, the real DOM:

```typescript
const input: HTMLInputElement =
  fixture.nativeElement.querySelector('input[type="email"]');

console.log('  touched before :', c.signupForm.email().touched());

input.value = 'typed@example.com';
input.dispatchEvent(new Event('input'));
input.dispatchEvent(new Event('blur'));
fixture.detectChanges();

console.log('  model email    :', c.model().email);
console.log('  touched after  :', c.signupForm.email().touched());
console.log('  valid          :', c.signupForm.email().valid());
```

```text
  touched before : false
  model email    : typed@example.com
  touched after  : true
  valid          : true
```

Typing updates the model, and `blur` sets `touched`. Exactly what you'd hope.

## Cross-Field Validation, For Free

**Does cross-field validation re-run when the _other_ field changes?**

This is the bit that has annoyed me for years. In Reactive Forms, your "passwords match" validator sits on `confirmPassword` - so when the user edits `password`, nothing re-runs. You end up subscribing to `valueChanges` and manually calling `updateValueAndValidity()`.

The rule itself is four lines, and the only interesting part is `valueOf`:

```typescript
validate(path.confirmPassword, ({ value, valueOf }) =>
  value() !== valueOf(path.password)
    ? { kind: 'mismatch', message: 'Passwords do not match' }
    : null,
);
```

So I set both fields to match, then changed only the **password** and looked at the _confirm_ field:

```typescript
c.signupForm.password().value.set('hunter2hunter2');
c.signupForm.confirmPassword().value.set('hunter2hunter2');
console.log('  after matching     :', messages(c.signupForm.confirmPassword()));

// Change the OTHER field. Does confirmPassword notice?
c.signupForm.password().value.set('something-else');
console.log('  after changing pwd :', messages(c.signupForm.confirmPassword()));
```

```text
  after matching     : []
  after changing pwd : [ 'Passwords do not match' ]
```

**It just re-ran.** Because `valueOf(path.password)` is a signal read, the validator depends on that field, and Angular re-runs it when the dependency changes. No subscription, no manual call, no memory leak to forget about.

That single behaviour is most of why I'd use Signal Forms.

## Conditional Rules with applyWhen

**Does `applyWhen` add and remove validators reactively?**

My signup page has a plan switch, and people flip it both ways. In Reactive Forms that means `setValidators`, then `clearValidators`, then `updateValueAndValidity()` on every flip - and if you forget the clearing half, a pro-only rule stays glued to a coupon box the user can no longer see, holding the whole form invalid with nothing red on screen to explain it. **So the interesting half of this test is flipping back, not flipping forward.**

```typescript
console.log('  plan=free, coupon errors :', messages(c.signupForm.couponCode()));
c.signupForm.plan().value.set('pro');
console.log('  plan=pro,  coupon errors :', messages(c.signupForm.couponCode()));
c.signupForm.couponCode().value.set('NOPE');
console.log('  bad format               :', messages(c.signupForm.couponCode()));
c.signupForm.couponCode().value.set('PRO-1234');
console.log('  good format              :', messages(c.signupForm.couponCode()));

// Flip back to free. Do the pro-only rules actually go away?
c.signupForm.couponCode().value.set('');
c.signupForm.plan().value.set('free');
console.log('  back to free             :', messages(c.signupForm.couponCode()));
```

```text
  plan=free, coupon errors : []
  plan=pro,  coupon errors : [ 'Pro needs a coupon code' ]
  bad format               : [ 'Format: PRO-1234' ]
  good format              : []
  back to free             : []
```

Flip the plan, the rules appear. Flip back - with the coupon box emptied again - and they're gone. No rebuilding the form.

That emptying is not tidying up, it's the point. A valid coupon passes whether the rule is attached or not, so **it takes an empty field to prove the `required` genuinely left.**

## Arrays with applyEach

**Do array rows added at runtime get validated?**

This is the one I expected to break. With `FormArray` you attach the validators inside every `push()`, so the day a second push site appears and someone forgets them, you get a row that silently validates nothing and junk in the database. **I wanted to watch a rule catch a row that was born ten minutes after the form was.**

Remember the rules were declared once, with `applyEach`, before any row existed:

```typescript
applyEach(path.team, (member) => {
  required(member.email, { message: 'Team member needs an email' });
  email(member.email, { message: 'Invalid team member email' });
});
```

Now add two rows at runtime and poke the first one:

```typescript
c.addTeamMember();
c.addTeamMember();
fixture.detectChanges();

console.log('  rows          :', c.model().team.length);
console.log('  row 0 errors  :', messages(c.signupForm.team[0].email()));
c.signupForm.team[0].email().value.set('not-an-email');
console.log('  row 0 bad     :', messages(c.signupForm.team[0].email()));
c.signupForm.team[0].email().value.set('team@example.com');
console.log('  row 0 fixed   :', messages(c.signupForm.team[0].email()));
```

```text
  rows          : 2
  row 0 errors  : [ 'Team member needs an email' ]
  row 0 bad     : [ 'Invalid team member email' ]
  row 0 fixed   : []
```

Note `signupForm.team[0].email()` - you index the field tree like a normal array.

`applyEach` covers rows that didn't exist when the form was created. Adding a row is just `model.update(...)` with a longer array - there's no `FormArray.push()` equivalent to remember.

## `disabled` and `readonly` Turn Validation Off

**Does `disabled` suppress validation, or only grey out the input?**

I ask because `disable()` in Reactive Forms quietly does three jobs at once. It stops validation, it greys the input, and it drops the control out of `form.value`. **I needed to know which of those three the new `disabled` still does**, because my submit payload depends on the answer.

To answer that cleanly I gave the coupon field an **unconditional** rule - one that lives outside the `applyWhen` block, so it always applies:

```typescript
// always applies, regardless of plan
minLength(path.couponCode, 4, { message: 'Coupon is too short' });

// but the field is switched off on the free plan
disabled(path.couponCode, {
  when: ({ valueOf }) => valueOf(path.plan) === 'free',
});
```

Then I put a 2-character value in it and looked at both plans.

```typescript
c.signupForm.couponCode().value.set('ab');

console.log('  --- plan = free (disabled) ---');
console.log('  disabled     :', c.signupForm.couponCode().disabled());
console.log('  field valid  :', c.signupForm.couponCode().valid());
console.log('  field errors :', messages(c.signupForm.couponCode()));
console.log('  value kept   :', JSON.stringify(c.model().couponCode));

c.signupForm.plan().value.set('pro');
console.log('  --- plan = pro (enabled) ---');
console.log('  disabled     :', c.signupForm.couponCode().disabled());
console.log('  field valid  :', c.signupForm.couponCode().valid());
console.log('  field errors :', messages(c.signupForm.couponCode()));
```

```text
  --- plan = free (disabled) ---
  disabled     : true
  field valid  : true
  field errors : []
  value kept   : "ab"
  --- plan = pro (enabled) ---
  disabled     : false
  field valid  : false
  field errors : [ 'Coupon is too short', 'Format: PRO-1234' ]
```

Two things worth pinning to your monitor.

First: **`disabled` switches validation off entirely.** The field is "valid" with rubbish in it. That's usually what you want - a hidden coupon box shouldn't block the form.

Second, and this is the sharp edge: **the value is still there.** Look at `value kept : "ab"`. That `"ab"` stays in the model, and it will happily ride along to your server in the submit payload. Disabled means "don't validate and don't let the user type", not "pretend this doesn't exist". If your backend trusts what it receives, clear the field when you disable it.

**Is `readonly` any different?**

Reactive Forms has no `readonly` concept at all. You bind `[readonly]` on the input yourself and the validators carry on happily underneath, which is nothing like what `disable()` does, **so I had no old habit to lean on here.**

Same experiment, different switch - a required field that goes readonly on the free plan:

```typescript
required(path.referralCode, { message: 'Referral code is required' });
readonly(path.referralCode, {
  when: ({ valueOf }) => valueOf(path.plan) === 'free',
});
```

```typescript
console.log('  --- plan = free (readonly) ---');
console.log('  readonly     :', c.signupForm.referralCode().readonly());
console.log('  field valid  :', c.signupForm.referralCode().valid());
console.log('  field errors :', messages(c.signupForm.referralCode()));

c.signupForm.plan().value.set('pro');
console.log('  --- plan = pro (editable) ---');
console.log('  readonly     :', c.signupForm.referralCode().readonly());
console.log('  field valid  :', c.signupForm.referralCode().valid());
console.log('  field errors :', messages(c.signupForm.referralCode()));
```

```text
  --- plan = free (readonly) ---
  readonly     : true
  field valid  : true
  field errors : []
  --- plan = pro (editable) ---
  readonly     : false
  field valid  : false
  field errors : [ 'Referral code is required' ]
```

Same deal. Validation off while readonly.

**Does it reach the real DOM?**

The schema says the field is off, and way back in the template I claimed `[formField]` pushes that down to the element. **Worth actually checking**, because if it doesn't I am back to binding `[disabled]` myself and keeping two things in sync.

```typescript
const coupon: HTMLInputElement =
  fixture.nativeElement.querySelectorAll('input[type="text"]')[1];

console.log('  input disabled attr :', coupon.disabled);
c.signupForm.plan().value.set('pro');
fixture.detectChanges();
console.log('  after switching pro :', coupon.disabled);
```

```text
  input disabled attr : true
  after switching pro : false
```

Yes - the actual `disabled` attribute on the `<input>`, flipping reactively. You don't bind it yourself.

One small note that comes from the type definitions rather than my test run: passing a bare function to these is **deprecated**. The `.d.ts` carries the tag `@deprecated Passing a function or string directly to 'disabled' is deprecated. Use '{ when: ... }' instead.` So use the config object:

```typescript
// deprecated
disabled(path.couponCode, ({ valueOf }) => valueOf(path.plan) === 'free');

// do this
disabled(path.couponCode, { when: ({ valueOf }) => valueOf(path.plan) === 'free' });
```

Plenty of tutorials still show the first form.

The same typings carry the same kind of note on `readonly` and on a third switch I didn't test, `hidden` - the three are declared side by side and all take a `{ when: ... }` config object.

They also spell out why validation goes quiet. Both `readonly` and `hidden` are documented as fields that **don't contribute to the validation, touched or dirty state of their parent** - so a rule on a switched-off field can't hold the form back. That's the typings talking, not my test run, but it matches exactly what I measured for `disabled` and `readonly` above.

## Async Validation

Everything so far answered instantly. Real signup forms do not - somewhere there is a call asking the server whether a username is free, and an answer that arrives late is a very different problem from an answer that is wrong. **It is also where the nasty surprise turned out to live**, so this is the part I poked hardest.

I wired the username up to a fake "is this taken?" endpoint with `validateAsync`. This is the wordiest API in the post, so here it is in full - it builds an Angular `resource()` and maps the result to errors:

```typescript
validateAsync(path.username, {
  // undefined means "don't run the check yet"
  params: ({ value }) => (value().length >= 3 ? value() : undefined),
  factory: (params) =>
    resource({
      params: () => params(),
      loader: ({ params }) => checkUsername(params as string),
    }),
  onSuccess: (result) =>
    result?.taken ? { kind: 'taken', message: 'That username is taken' } : null,
  onError: () => ({ kind: 'offline', message: 'Could not reach the server' }),
});
```

`checkUsername` is my stand-in for a real API:

```typescript
const TAKEN = ['admin', 'root', 'webmaster'];

export async function checkUsername(name: string): Promise<{ taken: boolean }> {
  await new Promise((r) => setTimeout(r, 50));
  return { taken: TAKEN.includes(name.toLowerCase()) };
}
```

**What does it look like while it runs?**

The Reactive Forms version of this is an `AsyncValidatorFn` plus a `loading` boolean I set and reset by hand on every path out of the request. **So the thing to watch here is the in-flight window** - because showing "That username is taken" before the server has answered is the kind of thing users screenshot.

```typescript
c.signupForm.username().value.set('webmaster');
console.log('  immediately -> pending:', c.signupForm.username().pending());

await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();

console.log('  after wait  -> pending:', c.signupForm.username().pending());
console.log('  after wait  -> errors :', messages(c.signupForm.username()));

c.signupForm.username().value.set('brand-new-name');
await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();
console.log('  free name   -> errors :', messages(c.signupForm.username()));
```

```text
  immediately -> pending: true
  after wait  -> pending: false
  after wait  -> errors : [ 'That username is taken' ]
  free name   -> errors : []
```

Clean. And `pending()` is just a signal, which is why the spinner back in the template was a plain `@if` - no subscription, no loading flag to reset.

**Why does a completely filled form still report `valid: false`?**

This one nearly went into the post as a different finding. I was checking whether a disabled-but-invalid field poisons the whole form, saw `valid: false`, and started writing that down.

It was wrong. The form was invalid because the **async username check hadn't finished** - nothing to do with the disabled field. Adding one `await` to the test told a completely different story:

```typescript
fillValidForm(c, 'brandnewuser');
c.signupForm.couponCode().value.set('ab'); // too short, but disabled on free

console.log('  before await -> pending:', c.signupForm().pending());
console.log('  before await -> valid  :', c.signupForm().valid());

await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();

console.log('  plan         :', c.model().plan);
console.log('  coupon value :', JSON.stringify(c.model().couponCode));
console.log('  after await  -> pending:', c.signupForm().pending());
console.log('  after await  -> valid  :', c.signupForm().valid());
```

```text
  before await -> pending: true
  before await -> valid  : false
  plan         : free
  coupon value : "ab"
  after await  -> pending: false
  after await  -> valid  : true
```

Once it settles, the form is valid - still on the free plan, still with `"ab"` sitting in the disabled coupon field.

So: **while any async validator is pending, your form reports `valid: false`.** If you're wondering why a fully filled form looks invalid, check `pending()` before you go hunting for a broken rule.

Bonus takeaway from the type definitions: **`valid()` is not `!invalid()`.** The `.d.ts` spells it out - `valid()` is true when there are no errors *and* no pending validators, while `invalid()` is true only when there are actual errors. During a pending check, both are false at the same time. So `@if (!field().valid())` and `@if (field().invalid())` are different questions, and the template in this post asks the second one on purpose.

## Submitting

**Does `submit()` run my action when the form is invalid?**

A Reactive Forms submit handler opens with a guard clause, because nothing else stops the submit running on a broken form. **Here I want to see what happens with no guard at all**, since one forgotten guard means a half-empty payload hitting the API.

Submit a completely empty form and see whether `saved` ever gets set:

```typescript
c.onSubmit(new Event('submit'));
await new Promise((r) => setTimeout(r, 100));
console.log('  form valid :', c.signupForm().valid());
console.log('  saved      :', c.saved());
```

```text
  form valid : false
  saved      : null
```

No. It refuses. You don't have to write `if (form.invalid) return;`.

**Does a valid form actually go through?**

Worth checking the happy path too, otherwise "it refuses" is not much of a compliment. Fill the form properly, wait for the username check to land, then submit:

```typescript
fillValidForm(c, 'brandnewuser');
await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();
console.log('  form valid :', c.signupForm().valid());

c.onSubmit(new Event('submit'));
await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();
console.log('  saved      :', c.saved());
```

```text
  form valid : true
  saved      : brandnewuser
```

It runs the action and hands it the value. Nothing surprising - which is exactly what you want from the boring case.

Keep an eye on that `await` before the check, though. Take it away and this same test turns into the nasty surprise at the end of the post.

**Can the server push an error back onto a specific field?**

This is my favourite small feature, because of what it replaces. Some things only the server knows - the username was free when you checked it and taken by the time you posted - and today that means unpicking the HTTP error, calling `setErrors` on the control by hand, and remembering to clear it on the next keystroke. **The question is whether a server error can just live on a field like an ordinary one.**

Your action returns errors that point at a field. This is also the inside of `onSubmit`, the handler every test so far has been calling - note what it doesn't pass, anything beyond `action`. That turns out to matter:

```typescript
submit(this.signupForm, {
  action: async (f) => {
    const data = f().value();
    if (data.username.toLowerCase() === 'nope') {
      return [{
        fieldTree: this.signupForm.username,
        kind: 'server',
        message: 'The server rejected that username',
      }];
    }
    this.saved.set(data.username);
    return undefined;
  },
});
```

The test fills the form with the one username my fake server hates:

```typescript
fillValidForm(c, 'nope');
await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();
console.log('  form valid before submit :', c.signupForm().valid());

c.onSubmit(new Event('submit'));
await new Promise((r) => setTimeout(r, 300));
fixture.detectChanges();

console.log('  username errors :', messages(c.signupForm.username()));
console.log('  saved           :', c.saved());
```

```text
  form valid before submit : true
  username errors : [ 'The server rejected that username' ]
  saved           : null
```

A 409 from your API lands on the username input, next to the client-side messages, with no plumbing. Lovely.

## The Nasty Surprise

Every answer so far was either a pleasant surprise or no surprise at all. **This is the one that would have put a bug in production**, and it is the reason I wrote the post.

`fillValidForm` just drops a complete, valid payload into the model in one go:

```typescript
function fillValidForm(c: Signup, username: string) {
  c.model.set({
    username,
    email: 'me@example.com',
    password: 'hunter2hunter2',
    confirmPassword: 'hunter2hunter2',
    age: 30,
    plan: 'free',
    couponCode: '',
    referralCode: '',
    team: [],
  });
}
```

This time, fill the form and submit **immediately**, without waiting for the username check:

```typescript
fillValidForm(c, 'brandnewuser');
console.log('  pending at submit time :', c.signupForm().pending());

c.onSubmit(new Event('submit'));
await new Promise((r) => setTimeout(r, 400));
fixture.detectChanges();

console.log('  saved                  :', c.saved());
```

```text
  pending at submit time : true
  saved                  : brandnewuser
```

It does **not** wait. The form submitted while the username check was still in flight.

With a free username that's harmless. So I ran the same thing with `webmaster` - a name my fake server already has:

```typescript
fillValidForm(c, 'webmaster'); // 'webmaster' is taken on the "server"
console.log('  pending at submit time :', c.signupForm().pending());
console.log('  username errors now    :', messages(c.signupForm.username()));

c.onSubmit(new Event('submit'));
await new Promise((r) => setTimeout(r, 400));
fixture.detectChanges();

console.log('  username errors after  :', messages(c.signupForm.username()));
console.log('  saved                  :', c.saved());
```

```text
  pending at submit time : true
  username errors now    : []
  username errors after  : [ 'That username is taken' ]
  saved                  : webmaster
```

Read that carefully. At submit time the username had **no errors yet**, because the check hadn't come back. So the form counted as valid, the action ran, and `saved: webmaster` happened. The "That username is taken" error showed up **afterwards** - on a form that had already been submitted.

A user who types a name and hits Enter quickly can save a value your validator was about to reject. My fake check sleeps for 50ms. A real one crosses the network, and a pasted username followed by Enter beats that comfortably.

### Fix one: `ignoreValidators: 'none'`

My first instinct was that Angular had left me to sort this out myself. It hasn't. `submit()` takes an `ignoreValidators` option, and the type definitions - not my test run - describe all three settings:

```text
// from @angular/forms/types/_structure-chunk.d.ts
- 'pending': Will submit if there are no invalid validators, pending validators do not block submission (default)
- 'none': Will not submit unless all validators are passing, pending validators block submission
- 'all': Will always submit regardless of invalid or pending validators
```

Look at which one is the default. **The behaviour above isn't a missing feature, it's the default setting - and the default is the footgun.** One extra line turns it off:

```typescript
onSubmitStrict(event: Event) {
  event.preventDefault();
  submit(this.signupForm, {
    ignoreValidators: 'none',
    action: async (f) => {
      this.saved.set(f().value().username);
      return undefined;
    },
  });
}
```

Same impatient click, same taken username, through the strict handler:

```typescript
fillValidForm(c, 'webmaster'); // taken, but the check has not come back yet
console.log('  pending at submit time :', c.signupForm().pending());

c.onSubmitStrict(new Event('submit'));
await new Promise((r) => setTimeout(r, 400));
fixture.detectChanges();

console.log('  saved                  :', c.saved());
console.log('  username errors after  :', messages(c.signupForm.username()));
```

```text
  pending at submit time : true
  saved                  : null
  username errors after  : [ 'That username is taken' ]
```

Blocked. And it doesn't turn into a form that can never be submitted - a good username still gets through on the second click, once the check has landed:

```typescript
fillValidForm(c, 'brandnewuser');
c.onSubmitStrict(new Event('submit'));
await new Promise((r) => setTimeout(r, 400));
fixture.detectChanges();
console.log('  saved on impatient click :', c.saved());

// The check has settled now. Click again.
c.onSubmitStrict(new Event('submit'));
await new Promise((r) => setTimeout(r, 200));
console.log('  saved after retry        :', c.saved());
```

```text
  saved on impatient click : null
  saved after retry        : brandnewuser
```

That second click is the important line. **`'none'` refuses the click - it does not queue it.** The first click just quietly does nothing.

### Fix two: your own `pending()` guard

Which is exactly why I still like the hand-rolled version. Same job, one extra thing:

```typescript
onSubmitGuarded(event: Event) {
  event.preventDefault();
  if (this.signupForm().pending()) {
    this.blocked.set('Still checking - hang on a second.');
    return;
  }
  this.blocked.set(null);
  this.onSubmit(event);
}
```

Same taken username, same impatient click - but through the guarded handler, and then a retry once the check has landed:

```typescript
fillValidForm(c, 'webmaster');
c.onSubmitGuarded(new Event('submit'));
await new Promise((r) => setTimeout(r, 400));
fixture.detectChanges();

console.log('  blocked message :', c.blocked());
console.log('  saved           :', c.saved());
console.log('  errors now      :', messages(c.signupForm.username()));

// The check has settled by now. Try again.
c.onSubmitGuarded(new Event('submit'));
await new Promise((r) => setTimeout(r, 200));
console.log('  after retry     :', c.saved());
```

```text
  blocked message : Still checking - hang on a second.
  saved           : null
  errors now      : [ 'That username is taken' ]
  after retry     : null
```

Blocked on the first click, with `Still checking - hang on a second.` on screen. And when the user tries again after the check lands, the form is properly invalid, so it refuses on the merits.

That last `null` is `webmaster` being rejected on its own demerits, not the guard being stricter than Fix one - this test reuses the taken username on purpose. A free name goes straight through, because the guard just hands off to the normal `onSubmit` once nothing is pending.

`blocked` is an ordinary signal, so putting it on screen is one more `@if`:

{% raw %}

```html
@if (blocked()) {
  <p class="blocked">{{ blocked() }}</p>
}
```

{% endraw %}

Note that this one doesn't wait either. **Neither fix waits for the check - both just refuse.** The difference is that this version knows it refused, so it can say so. `ignoreValidators: 'none'` on its own gives the user a button that appears to do nothing.

### Fix three: disable the button

The cheapest of the three, and you already saw it back in the template - this is why that `pending()` was in there:

{% raw %}

```html
<button type="submit" [disabled]="signupForm().submitting() || signupForm().pending()">
  {{ signupForm().submitting() ? 'Saving…' : 'Sign up' }}
</button>
```

{% endraw %}

These three are complementary, not alternatives. The disabled button stops most people from clicking, `ignoreValidators: 'none'` is the backstop for the ones who get a click in anyway, and the `pending()` guard is what lets you say something out loud when they do.

## Summary

After one evening and 20 passing tests with Signal Forms in Angular 22:

- **Nothing to install, nothing marked experimental.** `import { form } from '@angular/forms/signals'` and go.
- **Cross-field validation re-runs by itself.** This alone justifies the switch - no more `valueChanges` subscriptions to keep two fields in sync.
- **Show errors on `touched()`**, because they exist from the first render.
- **`applyWhen` and `applyEach` are reactive**, including array rows added later.
- **`disabled` and `readonly` turn validation off but keep the value** - it still goes to your server.
- **A pending async validator makes the form report `valid: false`** - check `pending()` before debugging a rule. And per the typings, `valid()` is not `!invalid()`; during a pending check both are false.
- **`submit()` defaults to `ignoreValidators: 'pending'`, and that default is the footgun.** Pass `'none'` so a fast clicker can't save a value your async check is about to reject - and show them a message, because it refuses rather than waits.

The Angular team's advice is to leave existing Reactive Forms alone and write new forms with Signal Forms, and having built one, that feels right. It's less code, and the reactive bits I used to wire up by hand are simply free.

My friendly tip: whenever you add an async validator, **write a test that clicks submit before it resolves.** That's the whole bug, and it takes about six lines to catch. Ask your forms awkward questions - they'll answer honestly.
