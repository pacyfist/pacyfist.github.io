---
name: blog-post-writer
description: Use to write or edit a new blog post.
---

# Blog Post Writer

Write posts for pacyfist.dev, a Jekyll blog using the Chirpy theme.

## File layout

- Post: `_posts/YYYY-MM-DD-kebab-case-slug.md` - use today's date unless told otherwise.
  The slug is built from the keyword half of the title, not the whole title. See
  [The title and the slug](#the-title-and-the-slug).
- Header image: `assets/img/YYYY-MM-DD/main.jpg` - same date as the post.

## Frontmatter

Exactly this shape (no `date`, no `author` - the theme handles those):

```yaml
---
tags: ["lowercase", "specific", "3-5 of them"]
categories: ["broad", "two-max"]
title: "Keyword Half: Hook Half" # see The title and the slug, below
image:
  path: /assets/img/YYYY-MM-DD/main.jpg
  alt: A short, witty alt text - often a joke, not a literal description.
---
```

## The title and the slug

The title is the only part of the post most people ever see. It appears in search
results, in the browser tab, and in every shared link. It has two jobs, in this order:
match the phrase a stranger types into a search box, then earn the click.

**Every title is exactly two halves joined by a colon:**

```
Keyword half: Hook half
```

**The keyword half comes first and is the search phrase**, written the way a stranger
who has never read this blog would type it. Product names, version numbers, and the
task they are trying to do - `Angular 22 + Tailwind 4 + SCSS Setup`,
`SQL Server UUID Keys`, `Omarchy Keyboard Shortcuts`. Someone who does not know the
post exists has to be able to type roughly these words.

**The hook half is the playful part** and carries the one specific promise: the flag,
the number, the surprise, the trap. All the personality lives here.

**The whole title is 60 characters or fewer.** Google cuts titles off around there.
Count the characters, do not eyeball them. If it will not fit, shorten the hook half -
the keyword half is the part that has to survive.

**The keyword half names the task, not just the tools.** A post about wiring three
libraries together is searched for as "setup", a post about a broken drive as
"recovery", a post about an upgrade as "migration". If the reader's verb is missing
from the keyword half, nobody finds the post.

Worked examples, all measured:

| Instead of                                                                | Write                                                  |
| ------------------------------------------------------------------------- | ------------------------------------------------------ |
| Angular 22, Tailwind 4, and SCSS: The One Flag That Almost Does It For You | Angular 22 + Tailwind 4 + SCSS Setup: Still a Manual Job |
| Taming the UUID Beast: How to Avoid Clustered Index Fragmentation in SQL Server | SQL Server UUID Keys: Taming Index Fragmentation   |
| Omarchy Has 227 Shortcuts: Here's How I Remember Them                     | Omarchy Keyboard Shortcuts: How I Remember All 227      |

Each rewrite moves the searchable words to the front, adds the missing task word, and
lands under 60 characters. None of them lose the joke.

### When the post updates an older one

Repeat the older post's keyword half with the new version number, and link to the old
post from the opening. Two posts targeting `Angular 19 ... Setup` and
`Angular 22 ... Setup` do not compete - people search for their own version.

### The slug

The filename slug is built from the **keyword half only**. The hook never goes in the
slug.

- Lowercase, hyphen separated, **3 to 6 words, 50 characters or fewer**.
- Drop filler words: `the`, `a`, `and`, `for`, `you`, `to`, `with`, `that`, `it`.
- Keep version numbers - they are what people search for.

`Angular 22 + Tailwind 4 + SCSS Setup: Still a Manual Job`
becomes `angular-22-tailwind-4-scss-setup` (32 chars, 6 words).

### Measure before you commit

```bash
f=$(ls _posts/YYYY-MM-DD-*.md)
awk -F'"' '/^title:/{printf "title: %d chars (max 60) - %s\n", length($2), $2; exit}' "$f"
s=$(basename "$f" .md | cut -c12-)
printf "slug:  %d chars (max 50), %d words (max 6) - %s\n" \
  "${#s}" "$(echo "$s" | tr '-' '\n' | wc -l)" "$s"
```

Over either limit, cut the hook half - never the keyword half.

## The opening

Every post opens with a true short story from my life that drops the reader into the
problem and shows why the rest of the post is worth reading. That part never changes.

**The _move_ it uses changes every single time.** Run this first:

```bash
for f in $(ls _posts/*.md | tail -5); do
  echo "--- $f"; awk 'BEGIN{d=0} /^---$/{d++;next} d>=2 && NF {print; exit}' "$f"
done
```

Read those five openings, then pick a move from the table that **none of them use**:

| Move              | Shape                                          | A real one from this blog                                                                                    |
| ----------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Cold open         | Drop straight into the moment, no greeting     | "Last week I had a browser open on the wrong monitor and couldn't remember the shortcut to throw it across." |
| Confession        | Admit the ignorance or bad habit that led here | "Guess what? I've been living under a rock because I just found out…"                                        |
| Double-take       | Name something you love, then the twist        | "I love code review. I also love _finishing_ code review."                                                   |
| Contrarian        | Justify why this post exists at all            | "There are already several guides on setting up Angular 19 with Tailwind 4, so why another one?"             |
| Flashback         | Start years ago, land on today                 | "During my university days, I became fascinated with 3D graphics…"                                           |
| Straight question | Ask the reader, then answer honestly           | "This is a very good question. Do you know? Because I don't."                                                |
| Series handoff    | Pick up exactly where the last post stopped    | "So we have our 1.5GB table and we connected it to our Entity Framework Core."                               |
| Long-running itch | A problem that has been nagging for ages       | "I have been obsessing about something since I started creating APIs in ASP.NET Core."                       |

The table is a starting menu, not a limit - a fresh move that fits the story is better
than a forced fit from the list. Whatever you pick, the first sentence must contain a
concrete detail from the actual story: a specific machine, hour, error, or object.
Generic scene-setting ("As developers, we all know…") is not an opening.

The wording should be unique in every new post. Avoid repeating phrases from previous posts, even if they are true.

## Writing style

- Casual and friendly, like telling a story to a coworker.
- Be brief. Use simple words. Short sentences, short paragraphs (1-3 sentences).
- Explain concepts with everyday analogies understandable to every computer nerd, not just the specialists. Avoid jargon unless you define it in plain English.
- Use `##` headings to break the post into small steps. End with a `## Summary` section: a short bullet list of takeaways plus one friendly closing tip.
- Bold the key takeaway phrases. Humor is welcome; carry it in the words.
- **No emoji anywhere in the prose, headings, or summary.** The one exception is
  console output: if a command really printed `✔` or similar, quote it exactly as
  it came out. Real output is evidence, not decoration - never edit a glyph out of it.
- **No em dashes.** Write a plain hyphen `-` instead of `—`. Same for en dashes `–`.
  A hyphen with spaces around it does the same job: "it worked - eventually".
  The same exception applies: never rewrite a dash that appears inside real console
  output, a file path, a command, or a quoted error message.

## Console commands

Every console command must be followed by its result:

1. Show the command in a fenced block with the right language tag (`bash`, `powershell`, ...).
2. Show what it prints in a separate ```text block right after (or describe the outcome in one sentence if the output is empty/boring).
3. If you can safely run the command yourself, do it and paste the real output. If not, write realistic expected output and mark anything machine-specific with placeholders like `/dev/sdX2`.

## Header image (required for every post)

Every post needs `assets/img/YYYY-MM-DD/main.jpg`. You cannot generate images yourself, so:

1. Create the directory `assets/img/YYYY-MM-DD/`.
2. Add a `main.jpg.prompt.txt` file in it containing a ready-to-paste image generation
   prompt that fits the post's topic and the blog's playful tone. It opens with the size
   line, then a scene paragraph and a details paragraph, and closes with the style block.
   Both the size line and the style block are copied verbatim from below.
3. Reference `/assets/img/YYYY-MM-DD/main.jpg` in the frontmatter anyway.
4. At the end, clearly tell the user: the image is missing - generate it with the prompt in `main.jpg.prompt.txt`, save it as `main.jpg` in that folder, and delete the prompt file.
5. Hand them the normalize command below in that same message, and tell them to run it
   on the saved `main.jpg` before deleting the prompt file.

### Normalize the saved image

Generators treat the size line as a hint. Ask for 1280x720 and you may still get
1672x941 back. This command makes the file match no matter what came out of the
generator:

```bash
magick assets/img/YYYY-MM-DD/main.jpg -resize 1280x720^ -gravity center \
  -extent 1280x720 -quality 85 -strip assets/img/YYYY-MM-DD/main.jpg
```

`-resize 1280x720^` scales until the image *covers* the target, `-extent` crops the
overflow from the centre, and `-strip` drops the EXIF the generator attached. Running
it on a file that is already correct changes nothing, so it is safe to run twice.

The centre crop is why the size line asks for a wide banner composition: anything
important pushed against the top or bottom edge can be trimmed here.

### The size line

**Every prompt file begins with this line, copied character for character:**

```text
Wide 16:9 landscape banner, exactly 1280 x 720 pixels. Do not change the size or the aspect ratio.
```

Nothing goes before it. Do not reword it, do not soften it to "roughly" or "about",
and do not mention any other dimensions, ratios, or pixel counts anywhere else in the
prompt - a second number gives the generator something to negotiate with.

Every header on this blog gets cropped into the same card, banner, and social-preview
shapes. When one image arrives at a different size, it crops differently from its
neighbours, and the post list stops looking like one blog. Past headers came back at
1024x1024, 1536x1024, and 1672x941 precisely because the size was phrased as a
suggestion. 1280x720 is plain 720p, and at that size a header lands around 120 KB.

Expect the generator to ignore the line anyway - ChatGPT has returned 1672x941 for it
twice. The line is still worth writing, but the normalize step below is what actually
makes the size true.

The rest of the prompt describes the scene and never touches the size again.

### The style block

**Every prompt file ends with this block, copied character for character:**

```text
Style: hand-painted watercolor on white structural paper, the rough cold-press tooth and paper fibers visible through every wash. Transparent layered washes with soft blooms, granulating pigment, and a few dry-brush edges, bare white paper left for the highlights. Straight-on eye-level camera, shallow depth so the scene reads as a flat painted page and not a deep 3D world. Even soft daylight, pale washed shadows, everything in focus. Bare white paper background with deep navy, teal, amber, and coral pigment. Friendly and slightly whimsical. No text, letters, numbers, logos, or UI labels anywhere.
```

Do not reword it and do not describe the rendering style anywhere else in the prompt -
the scene paragraphs say what is in the picture, this block says what it looks like.

The fussy-sounding parts are the ones doing the work. "Straight-on eye-level camera"
and "everything in focus" kill the two variables that make consecutive headers look
unrelated: dutch angles and depth-of-field blur. "Deep navy, teal, amber, and coral" is
the palette the blog already drifted into on its own, so it is the thread tying new
headers to the older ones. Naming the paper twice - "white structural paper" and "bare
white paper background" - is what stops the generator from filling the empty areas with
a painted sky or a colour wash; the background is supposed to be the paper itself. And
watercolor does not produce legible letterforms, which is why the older photoreal header
ended up full of readable text and the painted ones do not.

Write the scene in painted terms too - a "key in loose amber washes", not a "golden key"
- so the scene description is not arguing with the style block.

### What never goes in the image

**No robot.** Not as a mascot, not as a helpful bystander, not holding a clipboard in
the corner. Image generators reach for a friendly robot whenever a prompt mentions
computers, automation, or AI, and it always arrives as a substitute for the actual
idea. Two headers in a row picked one up without being asked; in both, the robot could
be deleted without losing anything the picture was saying.

The same goes for the rest of the visual clip art of "tech": glowing brains, falling
green characters, circuit-board traces used as decoration, hooded figures at keyboards,
lightbulbs for ideas, and floating holographic interfaces.

**Illustrate the specific thing the post is about**, using the objects the post already
talks about - the corridor, the key, the coins, the drive, the keyboard. If a figure is
in the scene, it should be doing the thing the post describes. When a scene needs an
outside force, prefer an anonymous one (a hand reaching in from the edge) over inventing
a character to personify it.

A character is fine when the post has one: a person hitting the actual problem. What is
not fine is a mascot standing in for the concept because the concept was hard to draw.

## Checklist before finishing

- [ ] Filename date matches the image folder date and the frontmatter image path.
- [ ] Title is `Keyword half: Hook half`, keyword half first, and names the reader's task.
- [ ] Ran the measuring command: title is 60 chars or fewer, slug is 3-6 words and 50
      chars or fewer. Measured, not estimated.
- [ ] First paragraph opens with a true short story showing why the info is useful.
- [ ] Ran the last-five-openings command, and this post's opening move matches none of them.
- [ ] First sentence contains a concrete detail from the story, not generic scene-setting.
- [ ] Every command block is followed by its output.
- [ ] No emoji outside quoted console output - check, don't assume:
      `grep -P '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]' _posts/YYYY-MM-DD-*.md`
- [ ] No em or en dashes outside quoted output:
      `grep -n '[—–]' _posts/YYYY-MM-DD-*.md`
- [ ] Post reads casual, brief, simple words.
- [ ] Image exists, or prompt file is in place and the user was told to generate it,
      normalize it with the `magick` command, and then delete the prompt file.
- [ ] If `main.jpg` exists, it measures exactly 1280x720 - check, don't assume:
      `identify -format '%wx%h\n' assets/img/YYYY-MM-DD/main.jpg`
- [ ] The prompt file's first line is the size line, character for character - check,
      don't assume:
      `head -1 assets/img/YYYY-MM-DD/main.jpg.prompt.txt`
- [ ] The prompt file's last line is the style block, character for character:
      `tail -1 assets/img/YYYY-MM-DD/main.jpg.prompt.txt`
- [ ] No robot or other stock tech clip art in the prompt - check, don't assume:
      `grep -nEi 'robot|android|droid|cyborg|mascot|hologram|circuit board|glowing brain' assets/img/YYYY-MM-DD/main.jpg.prompt.txt`
      Any hit needs a real reason: the post itself is about that thing.
- [ ] No other size, ratio, or pixel count appears anywhere else in the prompt file:
      `grep -nEi '[0-9]+ ?[x×] ?[0-9]+|[0-9]+:[0-9]+|pixels?|aspect' assets/img/YYYY-MM-DD/main.jpg.prompt.txt`
      Only the first line may match.
