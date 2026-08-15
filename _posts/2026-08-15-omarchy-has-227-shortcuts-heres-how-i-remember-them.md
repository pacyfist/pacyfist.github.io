---
tags: ["omarchy", "hyprland", "keybindings", "linux", "cheatsheet"]
categories: ["linux", "desktop"]
title: "Omarchy Has 227 Shortcuts: Here's How I Remember Them"
image:
  path: /assets/img/2026-08-15/main.jpg
  alt: One key to rule them all, and in the darkness bind them.
---

Last week I had a browser open on the wrong monitor and couldn't remember the shortcut to throw it across. I pressed `SUPER + K`, got a wall of keybindings, and by the time I found the right line I'd forgotten why I wanted it.

A complete list is a dictionary, not a phrasebook. So I wrote the phrasebook — mostly for future me.

```bash
omarchy menu keybindings --print | grep -c '→'
```

```text
227
```

Two hundred and twenty-seven. Nobody memorises that. But you don't have to, because they aren't 227 random facts — they're a handful of rules with a lot of instances.

## The Pattern That Made It Click

Sort them by modifier and the logic falls out. **Each modifier has a job.**

| Modifier           | What it means                | Count |
| ------------------ | ---------------------------- | ----- |
| `SUPER`            | Act on what's in front of me | 42    |
| `SUPER CTRL`       | System controls              | 42    |
| `SUPER SHIFT`      | Move it, or launch an app    | 37    |
| `SUPER ALT`        | Groups and variants          | 25    |
| `SUPER SHIFT ALT`  | The second-tier version      | 25    |
| `SUPER CTRL ALT`   | Just tell me something       | 7     |
| `SUPER SHIFT CTRL` | The rare, decisive one       | 6     |

So `SUPER + 3` visits workspace three and `SUPER SHIFT + 3` throws the window there. `SUPER + RETURN` opens a terminal, `SUPER ALT + RETURN` opens one with tmux. `SUPER CTRL + W` is the network menu, not a window.

It isn't a perfect law — `ALT + TAB` and the media keys do their own thing — but it's right often enough to **guess a shortcut you've never used.**

## The Ten to Learn First

| Keys                | Action                          |
| ------------------- | ------------------------------- |
| `SUPER + RETURN`    | Terminal                        |
| `SUPER + SPACE`     | Omarchy menu                    |
| `SUPER ALT + SPACE` | Apps menu                       |
| `SUPER + W`         | Close window                    |
| `SUPER + F`         | Full screen                     |
| `SUPER + ←↑↓→`      | Move focus between windows      |
| `SUPER + 1…9`       | Switch workspace                |
| `SUPER SHIFT + 1…9` | Send this window to a workspace |
| `PRINT`             | Screenshot                      |
| `SUPER + K`         | Show every binding              |

**The arrows are the one that changes everything.** Once `SUPER + arrow` is automatic, your hand stops drifting to the mouse.

The two `SPACE` keys are worth separating in your head early: `SUPER + SPACE` is the **Omarchy menu**, the one with settings and system things in it. `SUPER ALT + SPACE` is the **app launcher**. I reach for the second one twenty times a day and the first one twice a week.

## Windows

| Keys                                          | Action                        |
| --------------------------------------------- | ----------------------------- |
| `SUPER + W`                                   | Close window                  |
| `CTRL ALT + DELETE`                           | Close every window            |
| `SUPER + F`                                   | Full screen                   |
| `SUPER ALT + F`                               | Full width                    |
| `SUPER CTRL + F`                              | Tiled full screen             |
| `SUPER + T`                                   | Float or tile this window     |
| `SUPER + J`                                   | Flip the split direction      |
| `SUPER + O`                                   | Pop out: float and pin on top |
| `SUPER + P`                                   | Pseudo window                 |
| `SUPER + L`                                   | Toggle workspace layout       |
| `SUPER CTRL + BACKSPACE`                      | Single-window square aspect   |
| `SUPER + LEFT MOUSE`                          | Drag to move                  |
| `SUPER + RIGHT MOUSE`                         | Drag to resize                |

`SUPER + T` is the escape hatch for a dialog that refuses to tile nicely.

### Resizing

`minus` and `equal` sit right where your browser's zoom keys already are, so resizing costs you no new finger memory.

| Keys                     | Action              |
| ------------------------ | ------------------- |
| `SUPER + minus`          | Expand width        |
| `SUPER + equal`          | Shrink width        |
| `SUPER SHIFT + equal`    | Expand height       |
| `SUPER SHIFT + minus`    | Shrink height       |
| Add `ALT`                | …by a little        |
| Add `CTRL`               | …by a lot           |
| `SUPER ALT + Home`       | Save this width     |
| `SUPER + Home`           | Restore saved width |

**Hold `SHIFT` and the same two keys work vertically instead**, and the `ALT` / `CTRL` variants give you three speeds without learning three more keys.

The `Home` pair is quietly the best thing here. Get a window to the width you like, `SUPER ALT + Home` to remember it, then `SUPER + Home` to snap back after you've inevitably messed it up.

## Focus and Movement

| Keys                   | Action                            |
| ---------------------- | --------------------------------- |
| `SUPER + ←↑↓→`         | Move focus in that direction      |
| `SUPER SHIFT + ←↑↓→`   | Swap the window in that direction |
| `ALT + TAB`            | Next window                       |
| `SHIFT ALT + TAB`      | Previous window                   |
| `CTRL ALT + TAB`       | Next monitor                      |
| `SHIFT CTRL ALT + TAB` | Previous monitor                  |

A curiosity if you read the raw list: `ALT + TAB` appears **twice**, once as "Focus on next window" and once as "Reveal active window on top". That isn't a mistake — both fire, so the window you land on also comes to the front.

## Workspaces

| Keys                       | Action                                       |
| -------------------------- | -------------------------------------------- |
| `SUPER + 1…9, 0`           | Go to workspace 1–10                         |
| `SUPER + TAB`              | Next workspace                               |
| `SUPER SHIFT + TAB`        | Previous workspace                           |
| `SUPER CTRL + TAB`         | Back to the last one                         |
| `SUPER + mouse wheel`      | Scroll through workspaces                    |
| `SUPER SHIFT + 1…9, 0`     | Send window to workspace 1–10                |
| `SUPER SHIFT ALT + 1…9, 0` | Send it there but stay put                   |
| `SUPER SHIFT ALT + ←↑↓→`   | Move this whole workspace to another monitor |
| `SUPER + S`                | Open the scratchpad                          |
| `SUPER ALT + S`            | Stash this window in the scratchpad          |

That third-from-last row is the one I went hunting for in the first place. The **scratchpad** is a drawer: throw a chat window in, forget it, pull it back with one key.

## Window Groups

| Keys                      | Action                            |
| ------------------------- | --------------------------------- |
| `SUPER + G`               | Group or ungroup                  |
| `SUPER ALT + G`           | Kick this window out of the group |
| `SUPER ALT + TAB`         | Next tab in the group             |
| `SUPER SHIFT ALT + TAB`   | Previous tab                      |
| `SUPER ALT + 1…5`         | Jump to tab 1–5                   |
| `SUPER ALT + ←↑↓→`        | Pull a window in from that side   |
| `SUPER CTRL + ← →`        | Move focus along the tabs         |
| `SUPER ALT + mouse wheel` | Spin through the tabs             |

Grouping stacks windows behind tabs, like a browser.

## Apps and Terminals

Three terminals, and each has its own cheat sheet:

| Keys                  | Terminal | Its keybindings  |
| --------------------- | -------- | ---------------- |
| `SUPER + RETURN`      | Plain    | `SUPER + K`      |
| `SUPER ALT + RETURN`  | tmux     | `SUPER ALT + K`  |
| `SUPER CTRL + RETURN` | Herdr    | `SUPER CTRL + K` |

Everything else lives on `SUPER SHIFT` plus a letter:

| Key | App          | Key | App           |
| --- | ------------ | --- | ------------- |
| `A` | ChatGPT      | `O` | Obsidian      |
| `B` | Browser      | `P` | Google Photos |
| `C` | Calendar     | `S` | Google Maps   |
| `D` | Docker       | `W` | Omawrite      |
| `E` | Email        | `X` | X             |
| `F` | File manager | `Y` | YouTube       |
| `G` | Signal       | `N` | Editor        |
| `M` | Music        | `/` | Passwords     |

**Add `ALT` for the second-tier version of the same thing.** `SUPER SHIFT ALT + B` is a private browser window, `+ E` starts a new email instead of opening the inbox, `+ F` opens the file manager in your current directory, `+ A` is Grok, `+ G` is WhatsApp, `+ M` is the music TUI, `+ X` posts to X.

Two more hide on `SUPER SHIFT CTRL`: `A` for the coding agent, `G` for Google Messages.

Inside a web app, `SHIFT ALT + D` downloads the video you're looking at and `SHIFT ALT + L` copies its URL.

Any binding you don't use is a free key to steal.

## Clipboard and Capture

| Keys                                    | Action                        |
| --------------------------------------- | ----------------------------- |
| `SUPER + C` / `SUPER + V` / `SUPER + X` | Copy, paste, cut              |
| `SUPER CTRL + V`                        | Clipboard history             |
| `SUPER CTRL + E`                        | Emoji picker                  |
| `SUPER + PRINT`                         | Colour picker                 |
| `PRINT`                                 | Screenshot                    |
| `ALT + PRINT`                           | Record the screen             |
| `SUPER CTRL + PRINT`                    | Pull text out of a screenshot |
| `SUPER CTRL + PERIOD`                   | Transcode a recording         |
| `SUPER CTRL + S`                        | Share                         |
| `SUPER ALT + [` / `SUPER ALT + ]`       | Webcam overlay smaller/bigger |

Copy and paste work the same in a terminal and in normal apps, so you can stop thinking about `CTRL+SHIFT+C`. And `SUPER CTRL + PRINT` drags a box over anything on screen and puts the text in your clipboard — **ideal for lifting an error message out of someone's screenshot.**

## Notifications and Reminders

| Keys                      | Action                    |
| ------------------------- | ------------------------- |
| `SUPER + COMMA`           | Dismiss the last one      |
| `SUPER SHIFT + COMMA`     | Dismiss all of them       |
| `SUPER ALT + COMMA`       | Invoke the last one       |
| `SUPER SHIFT ALT + COMMA` | Open notification history |
| `SUPER CTRL + COMMA`      | Do not disturb            |
| `SUPER CTRL + R`          | Set a reminder            |
| `SUPER CTRL ALT + R`      | Show reminders            |
| `SUPER SHIFT CTRL + R`    | Clear them                |

## System and Screen

`SUPER CTRL` is the busiest modifier on the machine, and it's almost all system menus:

| Keys                   | Action              | Keys                     | Action              |
| ---------------------- | ------------------- | ------------------------ | ------------------- |
| `SUPER CTRL + A`       | Audio               | `SUPER CTRL + P`         | Power               |
| `SUPER CTRL + B`       | Bluetooth           | `SUPER CTRL + Q`         | Calculator          |
| `SUPER CTRL + W`       | Network             | `SUPER CTRL + T`         | Activity            |
| `SUPER CTRL + D`       | Display             | `SUPER CTRL + H`         | Hardware menu       |
| `SUPER CTRL + C`       | Capture menu        | `SUPER CTRL + O`         | Toggle menu         |
| `SUPER CTRL + L`       | Lock                | `SUPER CTRL + I`         | Auto-lock on idle   |
| `SUPER CTRL + N`       | Night light         | `SUPER CTRL + SPACE`     | Background switcher |
| `SUPER CTRL + Z`       | Zoom in             | `SUPER CTRL ALT + Z`     | Reset zoom          |
| `SUPER CTRL + 1…9`     | Bar panels 1–9      | `SUPER SHIFT + SPACE`    | Hide the top bar    |
| `SUPER CTRL + DELETE`  | Laptop display      | `SUPER CTRL ALT + DELETE`| Display mirroring   |

Plus the appearance toggles and the little status queries:

| Keys                                 | Action                           |
| ------------------------------------ | -------------------------------- |
| `SUPER + slash` / `SUPER ALT + slash`| Monitor scaling up / down        |
| `SUPER + BACKSPACE`                  | Window transparency              |
| `SUPER SHIFT + BACKSPACE`            | Gaps between windows             |
| `SUPER SHIFT CTRL + SPACE`           | Theme menu                       |
| `SUPER + ESCAPE`                     | System menu                      |
| `SUPER CTRL ALT + T` / `+ B` / `+ W` | Time, battery, weather           |
| `SUPER CTRL ALT + D`                 | Calendar                         |

The laptop pair is the one I use daily: `SUPER CTRL + DELETE` kills the built-in screen when I dock, `SUPER CTRL ALT + DELETE` mirrors it when someone wants to see what I'm doing.

## Dictation

| Keys             | Action                  |
| ---------------- | ----------------------- |
| `SUPER CTRL + X` | Toggle dictation        |
| `F9`             | Push-to-talk while held |

`F9` is bound twice on purpose — once to start on press, once to stop on release — which is what makes it push-to-talk rather than a toggle.

## Media Keys

The printed keys on your keyboard do what they say. The useful part is the modifiers stacked on top:

| Keys                          | Action                       |
| ----------------------------- | ---------------------------- |
| `ALT + volume` / `ALT + brightness` | Smaller steps          |
| `SHIFT + brightness`          | Jump to minimum or maximum   |
| `SHIFT + mute`                | Switch audio output          |
| `SHIFT + play`                | Switch media source          |
| `ALT + play`                  | Next track                   |
| `SHIFT ALT + play`            | Previous track               |

`SHIFT + mute` to flip between speakers and headphones beats opening a menu every time something connects.

## Making It Yours

Omarchy configures Hyprland in **Lua**. Your keybindings live in one file, and out of the box it's nothing but helpful comments:

```bash
ls ~/.config/hypr/
```

```text
autostart.lua   hyprland.lua    hyprsunset.conf  looknfeel.lua  xdph.conf
bindings.lua    hyprlock.conf   input.lua        monitors.lua
```

Adding a binding is one line — keys, a readable description, and the command:

```lua
o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")
```

That middle argument matters more than it looks. **The `SUPER + K` popup isn't a manual, it's generated from your own config**, so a new binding documents itself:

```bash
omarchy menu keybindings --print | grep 'SSH'
```

```text
SUPER SHIFT + R                     → SSH
```

For apps, pass a table instead of a string and Omarchy wraps the launch properly:

```lua
o.bind("SUPER + B", "Browser", { launch = "chromium" })
```

Taking over a key that's already busy needs an unbind first. Skip it and **both bindings stay alive**. Here's what that looks like on `SUPER SHIFT + Y`, normally YouTube:

```text
SUPER SHIFT + Y                     → Blog test override
SUPER SHIFT + Y                     → YouTube
```

Two live bindings on one key, and nothing warns you. Add the unbind and it behaves:

```lua
hl.unbind("SUPER + SHIFT + Y")
o.bind("SUPER + SHIFT + Y", "Blog test override", "notify-send 'override'")
```

```text
SUPER SHIFT + Y                     → Blog test override
```

Hyprland reloads the instant you save, so check your work:

```bash
hyprctl configerrors
```

Silence means it's happy. **Run it every time** — a typo takes out the rest of the file without a word.

Two bigger escape hatches are documented right inside your own `bindings.lua`. Set `omarchy_default_bindings = false` in `hyprland.lua` to start from a blank slate, or `omarchy_preinstalled_bindings = false` to keep all the window management and drop every app and web-app key. That second one frees up most of `SUPER SHIFT` in a single line.

## Summary

- **Learn the modifiers, not the keys.** `SUPER` acts, `SHIFT` moves or launches, `CTRL` is the system, `ALT` is the variant.
- Start with the ten above; `SUPER + arrows` unlocks the rest.
- `SUPER + SPACE` is the Omarchy menu, `SUPER ALT + SPACE` is the app launcher. Keep those two straight.
- `SUPER + T` floats a window that won't tile. `SUPER + S` is a drawer for later.
- To rebind: `hl.unbind`, then `o.bind`, then `hyprctl configerrors`.

The tip I keep giving myself: **don't sit down and memorise 227 shortcuts.** Learn the pattern, pick a handful you'd use today, and let the rest arrive when you need them. That's how the mouse turns into something you only touch on purpose.
