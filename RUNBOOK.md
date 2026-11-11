# RUNBOOK — one project per run

The scheduled agent follows these steps exactly. Every run produces **one** new,
working, deployed project. Nothing is repeated: `registry.json` is the source of truth.

## Constants

| Thing | Value |
| --- | --- |
| GitHub owner | `Password123-blip` |
| Supabase project ref | `gkrzhaicrsmuixagezkm` |
| Hosting | GitHub Pages, built by the included Actions workflow |
| Live URL pattern | `https://password123-blip.github.io/<slug>/` |

## Steps

1. **Pick the idea.** Run `python3 run_next.py`. It prints the next unused slug and
   writes `specs/<slug>.json`. If it exits with `EXHAUSTED`, stop and report that the
   backlog needs more ideas — do not invent a duplicate.

2. **Generate the app.**
   ```bash
   python3 generate.py specs/<slug>.json builds/<slug>
   ```
   This writes a complete Next.js 14 + Tailwind + Supabase app, a SQL migration,
   a README and a GitHub Pages workflow.

3. **Verify it compiles** before publishing:
   ```bash
   cd builds/<slug> && npm install --no-audit --no-fund && npm run build
   ```
   A repo that does not build must never be published. If it fails, fix the spec and
   regenerate — do not patch the generated output by hand.

4. **Create the repo** with `GITHUB_CREATE_A_REPOSITORY_FOR_THE_AUTHENTICATED_USER`
   (public, no auto-init). Name it exactly the slug.

5. **Push every file** with `GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS`, **one file at a
   time, sequentially**. Do not parallelise pushes to the same branch — GitHub rejects
   them with "concurrent modifications". Skip `node_modules`, `.next`, `out`, `.git`.

6. **Apply the schema** with `supabase_apply_migration`:
   - `project_id`: `gkrzhaicrsmuixagezkm`
   - `name`: `<slug_snake>_init`
   - `query`: the contents of `supabase/migrations/0001_init.sql`
   Table names are already prefixed with the slug, so they never collide.

7. **Set the build secrets** so the deployed site is actually wired up. Get the repo
   public key with `GITHUB_GET_A_REPOSITORY_PUBLIC_KEY`, encrypt each value with
   PyNaCl `SealedBox`, and set them with `GITHUB_CREATE_OR_UPDATE_A_REPOSITORY_SECRET`:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (fetch with `supabase_get_publishable_keys`,
     use the `anon` entry)

8. **Enable Pages** with `GITHUB_CREATE_OR_UPDATE_GITHUB_PAGES_SITE`,
   `build_type: "workflow"`. Push a README tweak afterwards if the workflow did not
   trigger on its own.

9. **Confirm the deploy.** Poll
   `gh api repos/Password123-blip/<slug>/actions/runs?per_page=1` until the run
   concludes. Success = published. Failure = fix and re-run, do not report it as done.

10. **Update the registry.** Append to `created` in `registry.json` here, bump
    `last_updated`, and push. This is what prevents repeats.

## Hard rules

- One project per run. Never publish a repo that fails `npm run build`.
- Never reuse a slug that appears in `registry.json`.
- Never create a second Supabase project — the org is on the **free plan, limit 2
  active projects**, and both slots are taken. One shared project, prefixed tables.
- Never commit a key to a repo. Keys go in Actions secrets only.
- If any step fails, stop and report it. A half-published repo is worse than none.
