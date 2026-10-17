# ExerciseMenu Library (WordPress plugin)

Exercise guides and workout routines for exercisemenu.com, built the way
LoadMuscle links routines to exercises, with stricter quality control.

- **Exercises** at `/exercises/{slug}/`: demo GIF or MP4, target muscle, equipment, level,
  steps, form cues, mistakes, easier/harder versions, alternatives, and an automatic
  "routines that use this exercise" list.
- **Routines** at `/workout-routines/{slug}/`: day-by-day tables (exercise, sets, reps, rest).
  Every exercise name links to its guide. Days per week, exercise count and session length
  are calculated from the plan.
- **Articles ↔ exercises**: every exercise page lists the posts/pages that link to it
  ("Related articles"), and the post edit screen has an *Exercise links* box listing
  exercises the article names but doesn't link yet, with the URL ready to copy.
- **Library pages** `/exercises/` and `/workout-routines/`: filterable grids (muscle, equipment, level, goal).
- **Index control**: nothing reaches Google until you tick *Ready to index*.

## Install

1. Zip the `exercisemenu-library` folder and upload it in **Plugins → Add New → Upload Plugin**, then activate.
2. Go to **Settings → Permalinks** and click **Save** once (refreshes URLs).
3. Create a page with the slug `exercises` and only `[em_exercise_library]` as its content.
4. Create a page with the slug `workout-routines` and only `[em_routine_library]` as its content.
5. Go to **Tools → Exercise Library → Import**. This creates the 12 medicine ball exercises and the
   3-day routine as **drafts**. Running it again skips anything that already exists.

## Publishing an exercise

1. Buy the GIF on gymvisual.com (IDs are in `GYMVISUAL-PURCHASE-LIST.md` and on the Tools page).
2. Open the exercise, set the GIF as **Featured image**, and give it the alt text "{Exercise} exercise demonstration".
3. Watch the GIF and check the steps match what it shows. Edit any step that doesn't.
4. Sadia reviews the steps, cues and mistakes and adds her own coaching notes to the main content.
5. Publish, then tick **Ready to index** and update.

The **Tools → Exercise Library** table shows which exercises are still missing media or the ready flag.

### Faster pages: GIF → MP4 (recommended)

A 1080px GIF is often 2–5 MB; the same loop as MP4 is usually a small fraction of that. Convert it:

```
ffmpeg -i slam.gif -movflags +faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" slam.mp4
```

Upload the MP4 to the Media Library, paste its URL in **Demo video URL**, and keep the GIF as the
featured image (used as the poster and in grids). Pages with an MP4 also get `VideoObject`
schema; a GIF alone never earns a video result in Google.

## Routine plan format

```
# Day 1: Push and Core
medicine-ball-chest-pass | 3 | 10 | 45
medicine-ball-woodchop-squat | 3 | 8/side | 45
medicine-ball-dead-bug | 2 | 30s | 30
```

`slug | sets | reps | rest seconds`. Reps can be `10`, `8-12`, `10/side` or `30s`.
The edit screen flags bad lines and slugs that don't exist yet. Exercises that aren't
published show as plain text (no broken links) until they go live.

Put `[em_routine_plan]` in the routine's content where the day tables should appear;
without it they go at the end.

Session length = sets × (reps × 3 s, or the time given) + rest between sets + 30 s per
exercise for setup. Warm-up is not included.

## SEO behaviour

| Page | Indexed? | In sitemap? |
|---|---|---|
| Exercise / routine, *Ready to index* ticked | yes | yes |
| Exercise / routine, not ticked | noindex, follow | no |
| `/exercises/muscle/…`, `/equipment/…`, `/level/…`, `/workout-routines/goal/…` | noindex, follow | no |

Works with WordPress core sitemaps, Yoast SEO and Rank Math. It has been tested on
core WordPress only; with Yoast or Rank Math, open one unticked exercise and check its
robots tag once.

## Linking articles to exercises

Link the first mention of each exercise in an article to its `/exercises/{slug}/` page.
The *Exercise links* box on the post screen shows which named exercises are still unlinked
(it reads the last saved version). Links are recorded when a post is saved; after installing,
click **Tools → Exercise Library → Rescan articles** once so existing articles are picked up.

This adds more internal links per article than the ExerciseMenu article-writer skill's
3–4 link limit allows. Decide whether exercise-name links count toward that limit.

## Adding more exercises in bulk

Add a file `data/exercises-{batch}.json` (same shape as `exercises-medicine-ball.json`) or
`data/routines-{batch}.json`, then run the import again, or `wp em-library import` with WP-CLI.
