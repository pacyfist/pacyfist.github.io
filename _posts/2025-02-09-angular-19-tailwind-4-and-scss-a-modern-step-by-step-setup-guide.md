---
tags: ["typescript", "angular", "tailwind", "daisyui"]
categories: ["typescript", "angular"]
title: "Angular 19, Tailwind 4, and SCSS: A Modern, Step-by-Step Setup Guide"
image:
  path: /assets/img/2025-02-09/angular-tailwind.jpg
  alt: Crafting Cosmic Web Designs!
---




There are already several guides on setting up Angular 19 with Tailwind 4, so why another one? Because I despise CSS and always configure Angular with SCSS instead. That small change allows for much cleaner and more readable styles. Unfortunately, every guide I could find used plain old CSS. It makes sense, since the whole idea of Tailwind is to minimize writing CSS, but I still want SCSS, and that's final!

## Sources

First, a shout-out to some great guides that helped along the way:

- [Setting Up Tailwind CSS 4.0 in Angular v19.1: A Step-by-Step Guide](https://dev.to/manthanank/setting-up-tailwind-css-40-in-angular-v191-a-step-by-step-guide-258m)

- [Angular 19 SCSS, Angular Material & Tailwind v3 made easy](https://medium.com/@anuroop.suresh/angular-19-scss-angular-material-tailwind-made-easy-6ea8a3927fda)

- [Install Tailwind CSS with Angular](https://tailwindcss.com/docs/installation/framework-guides/angular)

- [Get started with Tailwind CSS](https://tailwindcss.com/docs/installation/using-postcss)

## Prerequisites

Before we begin, ensure you have the following installed:

### Node.js

I recommend using [nvm](https://github.com/nvm-sh/nvm) for easily managing Node versions.

```
nvm list available
nvm install 23.7.0
nvm use 23.7.0
```

### npm

Node Package Manager comes bundled with Node.js but usually requires an update.

```
npm install --global npm
```

### Angular CLI

The Command Line Interface for Angular is pretty much the primary tool for anyone working with Angular.

```
npm install --global @angular/cli
```

## Setting Up Your Angular Project

### Create a New Angular Project with SCSS Support

```
ng new my-project --style scss
cd .\my-project\
```

### Install Tailwind v4, PostCSS, and the Tailwind CSS PostCSS Plugin

```
npm install tailwindcss@4 @tailwindcss/postcss postcss
```

## Configuring Tailwind CSS

### Create postcss.config.json

Time to [configure](https://github.com/postcss/postcss-load-config) PostCSS. In the root of your Angular project (where your angular.json file is located), create a file named `postcss.config.json` with the following content:

```json
{
    "plugins": {
        "@tailwindcss/postcss": {}
    }
}
```
## Import Tailwind CSS Styles

### Import Tailwind Directives in styles.scss

Here, we must do something slightly different because we've chosen SCSS. Other tutorials show using the `@import` command, but in SCSS, this command is [depreciated](https://sass-lang.com/blog/import-is-deprecated/) and we should substitute it with `@use`.

Open the `src/styles.scss` file in your project (this is your global stylesheet) and add the following line:


```css
@use "tailwindcss";
```

## (Optional) Adding DaisyUI Component Library

For those who want a rich set of pre-built components, consider adding DaisyUI. It's a fantastic component library built on top of Tailwind CSS.

**Important Note**: As of my last update, DaisyUI v4 is designed for Tailwind CSS v3. However, the beta version of DaisyUI v5 is compatible with Tailwind CSS v4.

### Install DaisyUI

```
npm i -D daisyui@beta
```

### Include DaisyUI as a Plugin

Update your `src/styles.scss` file to include the DaisyUI plugin:

```css
@use "tailwindcss";
@plugin "daisyui";
```

Now, unfortunately, things get a little quirky. My VS Code keeps showing me a warning: `Unknown at rule @pluginscss(unknownAtRules)`, but that's it. Styles from DaisyUI work fine, so, for the moment, I'm comfortable ignoring this warning.


## Testing configuration

If we modify the `src/app/app.component.html` file like this:

```html
<main class="main">
  <div class="flex flex-col justify-center items-center p-16">
    <h1 class="text-3xl underline text-amber-700 mt-10">Hello world from Tailwind</h1>
    <div class="btn btn-primary mt-5">Hello world from DaisyUI</div>
  </div>
</main>
<router-outlet />
```

and run the application locally:

```
ng serve
```

We should see a correctly styled page.

