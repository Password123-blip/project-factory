# Project Factory

A pipeline that turns one idea into a live, working web app: GitHub repo, database
schema, and a deployed public URL — every run.

**Live catalogue:** see `registry.json` for everything published so far.

## What gets built

Every project is a real Next.js 14 app, not a template rename:

| Layer | Choice |
| --- | --- |
| Framework | Next.js 14, App Router, TypeScript |
| Styling | Tailwind CSS |
| Database | Supabase Postgres, row-level security |
| Hosting | GitHub Pages via Actions |

Each app has a landing page with a feature grid, a form that writes to Postgres, and a
list that reads back — so the deployed site actually does something on first visit.

## Files

| File | Purpose |
| --- | --- |
| `generate.py` | Turns a spec JSON into a complete app |
| `run_next.py` | Picks the next unused idea, writes its spec |
| `ideas.json` | Backlog of distinct project ideas |
| `registry.json` | Everything published — prevents repeats |
| `specs/` | One spec per project |
| `RUNBOOK.md` | The exact procedure each scheduled run follows |

## Reproduce one project

```bash
python3 run_next.py                                    # prints the slug
python3 generate.py specs/<slug>.json builds/<slug>    # builds the app
cd builds/<slug> && npm install && npm run build       # verify
```

Then follow `RUNBOOK.md` from step 4 to publish.

## Adding ideas

Append to `backlog` in `ideas.json`. Required shape:

```json
{
  "slug": "kebab-case-unique",
  "title": "Human Title",
  "category": "Category",
  "tagline": "One line under the title",
  "table": {
    "name": "entries",
    "singular": "entry",
    "plural": "entries",
    "fields": [
      { "name": "label_text", "label": "Label", "type": "text", "required": true, "placeholder": "hint" }
    ]
  },
  "features": [
    { "icon": "◆", "title": "Feature", "body": "One sentence." }
  ]
}
```

Field types supported: `text`, `int`, `number`, `bool`, `date`.

## Constraints baked into this design

- **Supabase free plan allows 2 active projects.** Both are already used by other apps,
  so every project here shares one database and gets its own slug-prefixed table.
- **Hosting is GitHub Pages, not Netlify.** Deploying from the build sandbox to Netlify
  is blocked at the network level (`api.netlify.com` is not on the egress allowlist).
  `netlify.toml` is still shipped in every project, so a Netlify import works later.
- **GitHub Actions is free and unmetered for public repos**, which is why the build runs
  there rather than in the sandbox.
