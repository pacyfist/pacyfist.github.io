---
tags: ["typescript", "angular", "tailwind", "daisyui", "tooling"]
categories: ["typescript", "angular"]
title: "Angular 22 + Tailwind 4 + daisyUI Setup: Two Commands"
image:
  path: /assets/img/2026-08-17/main.jpg
  alt: A toolbox where every single tool is already the right one for the job.
---

Setting up Tailwind in an Angular project used to be a small ritual. Install three packages, hand-write a PostCSS config, guess the right filename, edit the global stylesheet, then find out something in that list changed two versions ago.

In Angular 22 it is one flag.

So this post spends about ninety seconds on the setup, and the rest of it on the part nobody writes about: the tooling you get afterwards. Angular 22 ships more of it out of the box than you probably expect, including a Model Context Protocol server that most people have not noticed yet.

## The whole setup

Two commands and one line. Here is the first one:

```bash
npx @angular/cli@latest new tw-demo --style tailwind
```

```text
CREATE tw-demo/.prettierrc (161 bytes)
CREATE tw-demo/README.md (1459 bytes)
CREATE tw-demo/.editorconfig (314 bytes)
CREATE tw-demo/.gitignore (622 bytes)
CREATE tw-demo/angular.json (1906 bytes)
CREATE tw-demo/package.json (877 bytes)
CREATE tw-demo/tsconfig.json (908 bytes)
CREATE tw-demo/tsconfig.app.json (398 bytes)
CREATE tw-demo/tsconfig.spec.json (409 bytes)
CREATE tw-demo/.postcssrc.json (53 bytes)
CREATE tw-demo/.vscode/extensions.json (130 bytes)
CREATE tw-demo/.vscode/launch.json (470 bytes)
CREATE tw-demo/.vscode/tasks.json (978 bytes)
CREATE tw-demo/src/main.ts (222 bytes)
CREATE tw-demo/src/index.html (292 bytes)
CREATE tw-demo/src/styles.css (104 bytes)
CREATE tw-demo/src/app/app.css (0 bytes)
CREATE tw-demo/src/app/app.spec.ts (674 bytes)
CREATE tw-demo/src/app/app.ts (289 bytes)
CREATE tw-demo/src/app/app.html (20144 bytes)
CREATE tw-demo/src/app/app.config.ts (313 bytes)
CREATE tw-demo/src/app/app.routes.ts (77 bytes)
CREATE tw-demo/public/favicon.ico (15086 bytes)
- Installing packages (npm)...
✔ Packages installed successfully.
```

**`tailwind` is a first-class `--style` choice now**, sitting right next to `css` and `scss`. Picking it installs `tailwindcss`, `@tailwindcss/postcss` and `postcss`, writes the PostCSS config, and wires up your global stylesheet.

That config file is `.postcssrc.json`, in the project root:

```json
{
  "plugins": {
    "@tailwindcss/postcss": {}
  }
}
```

And `src/styles.css` arrives already pointed at Tailwind:

```css
/* You can add global styles to this file, and also import other style files */

@import "tailwindcss";
```

Now the second command, for daisyUI:

```bash
npm install -D daisyui
```

It pulls in a single package and prints the usual audit summary. It is a dev dependency because it only ever runs at build time.

And the one line. Add it to `src/styles.css`:

```css
@import "tailwindcss";
@plugin 'daisyui';
```

That is the entire setup. DaisyUI 5 is stable, so plain `daisyui` gets you 5.7.17.

## Proving it works

Drop something loud into `src/app/app.html`:

```html
<main class="flex flex-col items-center p-16">
  <h1 class="text-3xl underline text-amber-700 mt-10">
    Hello world from Tailwind
  </h1>
  <button class="btn btn-primary mt-5">Hello world from daisyUI</button>
</main>
```

```bash
npx ng build
```

```text
❯ Building...
/*! 🌼 daisyUI 5.7.17 */
✔ Building...
Initial chunk files | Names         |  Raw size | Estimated transfer size
main-SUZ2D2LY.js    | main          | 189.54 kB |                51.76 kB
styles-SGSIWLJR.css | styles        |  25.70 kB |                 4.60 kB

                    | Initial total | 215.25 kB |                56.36 kB

Application bundle generation complete. [3.203 seconds]
```

The little flower is daisyUI announcing itself, and 25 kB of CSS means it generated its theme. `ng serve` gives you an amber underlined heading above a properly styled button.

Setup over. Now the interesting part.

## Tool 1: Prettier is already installed

Look again at that file list. `CREATE tw-demo/.prettierrc`. Angular 22 does not just recommend Prettier, it ships it as a dev dependency and configures it:

```json
{
  "printWidth": 100,
  "singleQuote": true,
  "overrides": [
    {
      "files": "*.html",
      "options": {
        "parser": "angular"
      }
    }
  ]
}
```

That `parser: angular` override is the important bit. It teaches Prettier to read Angular template syntax instead of choking on `@if` blocks and `[property]` bindings.

**Add one plugin and it will also sort your Tailwind classes.**

```bash
npm install -D prettier-plugin-tailwindcss
```

Register it in `.prettierrc`:

```json
{
  "printWidth": 100,
  "singleQuote": true,
  "plugins": ["prettier-plugin-tailwindcss"],
  "overrides": [
    {
      "files": "*.html",
      "options": {
        "parser": "angular"
      }
    }
  ]
}
```

Here is a template with the classes in the order a human types them, which is to say no order at all:

```html
<main class="p-16 flex items-center flex-col">
  <h1 class="mt-10 underline text-3xl text-amber-700">
    Hello world from Tailwind
  </h1>
  <button class="mt-5 btn-primary btn">Hello world from daisyUI</button>
</main>
```

```bash
npx prettier --write src/app/app.html
```

```html
<main class="flex flex-col items-center p-16">
  <h1 class="mt-10 text-3xl text-amber-700 underline">
    Hello world from Tailwind
  </h1>
  <button class="btn-primary btn mt-5">Hello world from daisyUI</button>
</main>
```

Layout first, then spacing, then colour, then decoration. Every file in your project ends up in the same order, which means **class lists stop showing up as noise in code review**. Notice it also groups the daisyUI component classes ahead of the utilities.

## Tool 2: Angular ships an MCP server

This is the one I did not expect. Remember the `--ai-config` flag:

```bash
npx @angular/cli@latest new ai-demo --style tailwind --ai-config claude-code
```

```text
CREATE ai-demo/.postcssrc.json (53 bytes)
CREATE ai-demo/CLAUDE.md (2849 bytes)
CREATE ai-demo/.mcp.json (121 bytes)
CREATE ai-demo/.vscode/extensions.json (130 bytes)
```

Two files worth opening. The first is `CLAUDE.md`, a rules file that tells a coding agent how modern Angular actually works:

```text
- Always use standalone components over NgModules
- Must NOT set `standalone: true` inside Angular decorators. It's the default in Angular v20+.
- Do NOT set `changeDetection: ChangeDetectionStrategy.OnPush` explicitly. `OnPush` is the default in Angular v22+.
- Use signals for state management
- Use `input()` and `output()` functions instead of decorators
```

Given how many agents still confidently generate `app.component.ts` and `NgModule` boilerplate, letting the framework state its own current rules is a cheap win.

The second file is `.mcp.json`:

```json
{
  "mcpServers": {
    "angular-cli": {
      "command": "npx",
      "args": ["-y", "@angular/cli", "mcp"]
    }
  }
}
```

**`ng mcp` is a real command, and it does not appear in `ng --help`.** Here is what the server exposes:

```text
server: angular-cli-server 22.1.4
tools:
  - ai_tutor
  - get_best_practices
  - search_documentation
  - list_projects
  - onpush_zoneless_migration
  - run_target
  - devserver_start
  - devserver_stop
  - devserver_wait_for_build
```

So your agent can search angular.dev, read the official best practices, start and stop the dev server, wait for a build to finish, and run a migration. `--ai-config` takes `claude-code`, `cursor`, `gemini-cli`, `open-ai-codex`, `vscode`, or `none`, and you can pass several at once.

## Tool 3: daisyUI has its own MCP server

daisyUI plays the same game, with three options.

**Blueprint** is the official one. It is a paid product - the setup wants a license key and an email:

```bash
claude mcp add daisyui-blueprint --env LICENSE=YOUR_LICENSE_KEY --env EMAIL=YOUR_EMAIL -- npx -y daisyui-blueprint@latest
```

**Context7** is the free third-party option, and it indexes daisyUI along with everything else.

**Or skip MCP entirely.** daisyUI publishes an `llms.txt` file, which is its whole documentation flattened into one text file for a model to read:

```bash
curl -s -o /dev/null -w "%{http_code} %{size_download} bytes\n" https://daisyui.com/llms.txt
```

```text
200 79134 bytes
```

Seventy-nine kilobytes of component docs. Paste the URL into a prompt and ask for what you want. That is the zero-setup version and it costs nothing.

## Tool 4: The editor setup you did not have to write

Angular 22 writes `.vscode/extensions.json` for you:

```json
{
  "recommendations": ["angular.ng-template"]
}
```

That is the Angular Language Service, which gives you template type checking and go-to-definition inside HTML files. VS Code will prompt anyone who opens the project to install it.

**Add the Tailwind one yourself**, because the scaffold does not:

```json
{
  "recommendations": ["angular.ng-template", "bradlc.vscode-tailwindcss"]
}
```

Tailwind CSS IntelliSense gives you class autocomplete, hover previews of what a class actually does, and colour swatches in the margin. With daisyUI installed it picks up the component classes too.

One squiggle to silence. The CSS language server has never heard of `@plugin`, so it flags it as an unknown at-rule. Create `.vscode/settings.json`:

```json
{
  "css.lint.unknownAtRules": "ignore",
  "scss.lint.unknownAtRules": "ignore"
}
```

**Set both.** They are separate language configurations, and if you ever move a file to `.scss` the `css.` setting alone does nothing. That is why so many people report this fix "not working".

## Tool 5: A debugger that is already configured

`.vscode/launch.json` shows up in the scaffold too:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "ng serve",
      "type": "chrome",
      "request": "launch",
      "preLaunchTask": "npm: start",
      "url": "http://localhost:4200/"
    }
  ]
}
```

Press F5. It runs `npm start`, waits for the bundle, opens Chrome, and attaches the debugger. Breakpoints in your TypeScript work immediately, with no configuration written by you.

While you are in the browser, install **Angular DevTools**. It adds a component tree and a profiler that shows which components re-rendered and why, which is the fastest way to find the one signal that updates more than you thought.

## Tool 6: Theming without a config file

daisyUI 5 configures itself in CSS. Ask for the themes you want right in the `@plugin` line:

```css
@import "tailwindcss";
@plugin 'daisyui' {
  themes:
    light --default,
    dark --prefersdark,
    cupcake;
}
```

```text
/*! 🌼 daisyUI 5.7.17 */
styles-2FAIFFRX.css | styles        |  26.83 kB |                 4.77 kB
```

All three themes landed in the bundle, and `--prefersdark` wired up a `prefers-color-scheme` block, so dark mode follows the operating system with nothing else to do. Switching at runtime is one attribute: `<html data-theme="cupcake">`.

Your own theme is the same shape. Name it, set the parts you care about, and skip the rest:

```css
@import "tailwindcss";
@plugin 'daisyui';
@plugin 'daisyui/theme' {
  name: "pacyfist";
  default: true;
  --color-primary: oklch(55% 0.3 240);
  --radius-field: 0.25rem;
}
```

```text
styles-RKBWMY5P.css | styles        |  25.89 kB |                 4.62 kB
```

Two overrides, and every `btn-primary` in the app follows. **There is no `tailwind.config.js` anywhere in this post**, and that is not an omission - Tailwind 4 and daisyUI 5 both moved their configuration into CSS.

## Tool 7: The CLI commands you forget exist

Three of these are worth a minute each.

**Shell autocompletion.** The CLI will write it for you:

```bash
npx ng completion
```

```text
Set up Angular CLI autocompletion for your terminal.

Commands:
  ng completion script  Generate a bash and zsh real-time type-ahead autocompletion script.
```

**The build cache**, which is on by default and explains why the second build is so much faster than the first:

```bash
npx ng cache info
```

```text
Cache Information

Enabled           : Yes
Environment       : local
Path              : /home/you/projects/tw-demo/.angular/cache
Size on disk      : 965.77 kB
Effective Status  : Enabled (current machine)
```

**Upgrades**, which check your whole dependency tree rather than just bumping a number:

```bash
npx ng update
```

```text
Using package manager: npm
Collecting installed dependencies...
Found 20 dependencies.
We analyzed your package.json and everything seems to be in order. Good work!
```

Run it with no arguments any time you are curious. It only reports.

## Three small things that will confuse you

**Your first test fails after you edit the template.** The generated spec asserts on the default page:

```text
expect(compiled.querySelector('h1')?.textContent).toContain('Hello, tw-demo');
```

Replace `app.html` with your own markup and that assertion breaks. It is not Tailwind's fault. Also note the runner: Angular 21 made **vitest** the default, so Karma and Jasmine are gone.

**Generated components still get a stylesheet.** `ng generate component widget` creates `widget.css`, empty. With Tailwind you will mostly never open it. Pass `--inline-style` if the empty files bother you.

**Unused imports are a warning now.** Strip the default template and the compiler notices:

```text
▲ [WARNING] NG8113: All imports are unused

    src/app/app.ts:6:2:
      6 │   imports: [RouterOutlet],
        ╵   ~~~~~~~
```

Delete the import and it goes quiet.

## Summary

- **`ng new --style tailwind` does the whole Tailwind setup.** daisyUI is one more install and one `@plugin` line.
- The config file is **`.postcssrc.json`**, and there is **no `tailwind.config.js`** in Tailwind 4 at all.
- **Prettier ships with the scaffold.** Add `prettier-plugin-tailwindcss` and your class lists sort themselves.
- **`--ai-config` writes a rules file and an MCP config.** `ng mcp` is a real server with nine tools, and it is hidden from `ng --help`.
- daisyUI's official **Blueprint MCP server is paid**, but `llms.txt` is free and works in any prompt.
- The scaffold configures **the Angular Language Service and a Chrome debugger** for you. Add Tailwind IntelliSense and silence `unknownAtRules` in both `css.` and `scss.`.
- **Themes are CSS now**, including your own, with no config file to maintain.
- daisyUI 5 is stable, so **drop the `@beta` tag** you will see in older guides.

Closing tip: before you follow any Angular setup guide, run `ng version` and check the date on the guide. Three majors was enough to rename the component files, delete zone.js, swap the test runner, and turn a five step setup into a flag.
