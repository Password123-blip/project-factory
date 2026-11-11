#!/usr/bin/env python3
"""
Project factory: turns a spec JSON into a complete Next.js 14 + Tailwind + Supabase app.

Usage: python generate.py specs/<slug>.json <outdir>
"""
import json
import os
import sys
from pathlib import Path

R = {}  # rendered files: relative path -> content


def rep(text: str, ctx: dict) -> str:
    for k, v in ctx.items():
        text = text.replace(f"@@{k}@@", str(v))
    return text


def snake(s: str) -> str:
    return s.replace("-", "_")


def build(spec: dict, out: Path):
    ctx = {
        "SLUG": spec["slug"],
        "TITLE": spec["title"],
        "TAGLINE": spec["tagline"],
        "DESCRIPTION": spec["description"],
        "ACCENT": spec.get("accent", "#6366f1"),
        "ACCENT_SOFT": spec.get("accent_soft", "#eef2ff"),
        "CATEGORY": spec.get("category", "Web App"),
        "TABLE": f"{snake(spec['slug'])}_{spec['table']['name']}",
        "ENTITY": spec["table"]["singular"],
        "ENTITY_PLURAL": spec["table"]["plural"],
        "SCHEMA_SQL": schema_sql(spec, ctx_placeholder=True),
        "FEATURES_TSX": features_tsx(spec),
        "FORM_FIELDS_TSX": form_fields_tsx(spec),
        "LIST_COLUMNS_TSX": list_columns_tsx(spec),
        "SEED_ROWS": json.dumps(spec.get("seed", [])),
        "FIELD_DEFS": json.dumps(spec["table"]["fields"]),
    }

    files = {
        "package.json": PKG,
        "next.config.js": NEXT_CONFIG,
        "tsconfig.json": TSCONFIG,
        "tailwind.config.ts": TAILWIND,
        "postcss.config.js": POSTCSS,
        "netlify.toml": NETLIFY,
        ".gitignore": GITIGNORE,
        ".env.example": ENV_EXAMPLE,
        "lib/supabase.ts": SUPABASE_LIB,
        "app/globals.css": GLOBALS_CSS,
        "app/layout.tsx": LAYOUT,
        "app/page.tsx": PAGE,
        "components/EntryForm.tsx": ENTRY_FORM,
        "components/EntryList.tsx": ENTRY_LIST,
        "components/StatBar.tsx": STAT_BAR,
        "supabase/migrations/0001_init.sql": ctx["SCHEMA_SQL"],
        "README.md": README,
    }

    for rel, content in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(rep(content, ctx), encoding="utf-8")

    # write the spec alongside for provenance
    (out / "project.spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")


def sql_type(f: dict) -> str:
    t = f["type"]
    return {
        "text": "text",
        "int": "integer",
        "number": "numeric",
        "bool": "boolean",
        "date": "date",
        "timestamptz": "timestamptz",
    }.get(t, "text")


def schema_sql(spec: dict, ctx_placeholder=False) -> str:
    tbl = f"{snake(spec['slug'])}_{spec['table']['name']}"
    cols = []
    for f in spec["table"]["fields"]:
        null = "" if f.get("required", True) else " null"
        dflt = f" default {f['default']}" if "default" in f else ""
        cols.append(f"  {f['name']} {sql_type(f)}{dflt}{null}")
    col_block = ",\n".join(cols)

    seeds = []
    for row in spec.get("seed", [])[:6]:
        vals = []
        for f in spec["table"]["fields"]:
            v = row.get(f["name"], "")
            if f["type"] in ("int", "number"):
                vals.append(str(v) if v != "" else "null")
            elif f["type"] == "bool":
                vals.append("true" if v else "false")
            else:
                vals.append("'" + str(v).replace("'", "''") + "'")
        seeds.append("  (" + ", ".join(vals) + ")")
    seed_block = ""
    if seeds:
        names = ", ".join(f["name"] for f in spec["table"]["fields"])
        seed_block = (
            f"\ninsert into public.{tbl} ({names}) values\n"
            + ",\n".join(seeds)
            + ";\n"
        )

    return f"""-- {spec['title']} — schema
-- Safe to run more than once.

create extension if not exists "pgcrypto";

create table if not exists public.{tbl} (
  id uuid primary key default gen_random_uuid(),
{col_block},
  created_at timestamptz not null default now()
);

create index if not exists {tbl}_created_idx on public.{tbl} (created_at desc);

alter table public.{tbl} enable row level security;

drop policy if exists "{tbl}_read" on public.{tbl};
create policy "{tbl}_read" on public.{tbl} for select using (true);

drop policy if exists "{tbl}_insert" on public.{tbl};
create policy "{tbl}_insert" on public.{tbl} for insert with check (true);
{seed_block}"""


def features_tsx(spec: dict) -> str:
    out = []
    for f in spec.get("features", []):
        out.append(
            f"""        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-2xl">{f.get('icon', '◆')}</div>
          <h3 className="mt-3 font-semibold text-slate-900">{f['title']}</h3>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">{f['body']}</p>
        </div>"""
        )
    return "\n".join(out)


def form_fields_tsx(spec: dict) -> str:
    out = []
    for f in spec["table"]["fields"]:
        label = f["label"]
        name = f["name"]
        req = " required" if f.get("required", True) else ""
        if f["type"] == "bool":
            out.append(
                f"""          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" name="{name}" className="h-4 w-4 rounded border-slate-300" />
            {label}
          </label>"""
            )
        elif f["type"] in ("int", "number"):
            out.append(
                f"""          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
            <input type="number" name="{name}" step="any"{req}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900" />
          </div>"""
            )
        elif f["type"] == "date":
            out.append(
                f"""          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
            <input type="date" name="{name}"{req}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900" />
          </div>"""
            )
        else:
            ph = f.get("placeholder", "")
            out.append(
                f"""          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{label}</label>
            <input type="text" name="{name}" placeholder="{ph}"{req}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900" />
          </div>"""
            )
    return "\n".join(out)


def list_columns_tsx(spec: dict) -> str:
    out = []
    for f in spec["table"]["fields"][:3]:
        out.append(
            f"""              <div>
                <div className="text-xs uppercase tracking-wide text-slate-400">{f['label']}</div>
                <div className="text-slate-800">{{String(row.{f['name']} ?? '—')}}</div>
              </div>"""
        )
    return "\n".join(out)


# ---------------------------------------------------------------- templates

PKG = """{
  "name": "@@SLUG@@",
  "version": "1.0.0",
  "private": true,
  "description": "@@TAGLINE@@",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "@supabase/supabase-js": "^2.45.4",
    "next": "14.2.15",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/node": "^20.14.10",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.39",
    "tailwindcss": "^3.4.6",
    "typescript": "^5.5.3"
  }
}
"""

NEXT_CONFIG = """/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
};

module.exports = nextConfig;
"""

TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

TAILWIND = """import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        accent: "@@ACCENT@@",
        accentSoft: "@@ACCENT_SOFT@@",
      },
    },
  },
  plugins: [],
};
export default config;
"""

POSTCSS = """module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
"""

NETLIFY = """[build]
  command = "npm run build"
  publish = ".next"

[[plugins]]
  package = "@netlify/plugin-nextjs"
"""

GITIGNORE = """node_modules/
.next/
out/
.env
.env.local
.DS_Store
*.log
next-env.d.ts
"""

ENV_EXAMPLE = """# Supabase — copy to .env.local and fill in from your project settings
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
"""

SUPABASE_LIB = """import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const TABLE = "@@TABLE@@";

export const isConfigured = Boolean(url && anon);

let cached: SupabaseClient | null = null;

export function supabase(): SupabaseClient {
  if (!isConfigured) {
    throw new Error("Supabase env vars are not set. See .env.example");
  }
  if (!cached) {
    cached = createClient(url as string, anon as string, {
      auth: { persistSession: false },
    });
  }
  return cached;
}

export type Row = Record<string, unknown> & { id: string; created_at: string };
"""

GLOBALS_CSS = """@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --accent: @@ACCENT@@;
  --accent-soft: @@ACCENT_SOFT@@;
}

html {
  scroll-behavior: smooth;
}

body {
  background: #f8fafc;
  color: #0f172a;
}
"""

LAYOUT = """import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "@@TITLE@@",
  description: "@@TAGLINE@@",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
"""

PAGE = """import EntryForm from "@/components/EntryForm";
import EntryList from "@/components/EntryList";
import { isConfigured } from "@/lib/supabase";

export default function Home() {
  return (
    <main className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <span
              className="grid h-9 w-9 place-items-center rounded-lg text-white"
              style={{ background: "var(--accent)" }}
            >
              ◆
            </span>
            <span className="font-semibold tracking-tight">@@TITLE@@</span>
          </div>
          <span className="rounded-full bg-accentSoft px-3 py-1 text-xs font-medium" style={{ color: "var(--accent)" }}>
            @@CATEGORY@@
          </span>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-6 py-16">
        <p className="text-sm font-medium" style={{ color: "var(--accent)" }}>
          @@TAGLINE@@
        </p>
        <h1 className="mt-3 max-w-3xl text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
          @@DESCRIPTION@@
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-slate-600">
          A working Next.js app with a live Supabase backend. Add a @@ENTITY@@ below and it
          is stored in Postgres with row-level security, then read straight back.
        </p>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-16">
        <div className="grid gap-4 sm:grid-cols-3">
@@FEATURES_TSX@@
        </div>
      </section>

      {!isConfigured && (
        <div className="mx-auto mb-10 max-w-5xl px-6">
          <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900">
            <strong>Supabase not configured.</strong> Copy <code>.env.example</code> to{" "}
            <code>.env.local</code> and add your project URL and anon key. The UI below is
            fully functional once those are set.
          </div>
        </div>
      )}

      <section className="mx-auto grid max-w-5xl gap-6 px-6 pb-24 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <EntryForm />
        </div>
        <div className="lg:col-span-3">
          <EntryList />
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white py-8">
        <div className="mx-auto max-w-5xl px-6 text-sm text-slate-500">
          @@TITLE@@ — built with Next.js, Tailwind CSS and Supabase.
        </div>
      </footer>
    </main>
  );
}
"""

ENTRY_FORM = """"use client";

import { useState } from "react";
import { supabase, TABLE, isConfigured } from "@/lib/supabase";

type FieldDef = {
  name: string;
  label: string;
  type: string;
  required?: boolean;
  placeholder?: string;
};

const FIELDS: FieldDef[] = @@FIELD_DEFS@@;

export default function EntryForm() {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const payload: Record<string, unknown> = {};

    for (const f of FIELDS) {
      const raw = data.get(f.name);
      if (f.type === "bool") {
        payload[f.name] = data.get(f.name) === "on";
      } else if (raw === null || raw === "") {
        if (f.required) {
          setMsg(`${f.label} is required.`);
          return;
        }
      } else if (f.type === "int") {
        payload[f.name] = parseInt(String(raw), 10);
      } else if (f.type === "number") {
        payload[f.name] = parseFloat(String(raw));
      } else {
        payload[f.name] = String(raw);
      }
    }

    if (!isConfigured) {
      setMsg("Add your Supabase keys to .env.local first.");
      return;
    }

    setBusy(true);
    setMsg(null);
    const { error } = await supabase().from(TABLE).insert(payload);
    setBusy(false);

    if (error) {
      setMsg(error.message);
      return;
    }
    form.reset();
    setMsg("Saved.");
    window.dispatchEvent(new Event("entry:created"));
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 className="text-lg font-semibold text-slate-900">Add a @@ENTITY@@</h2>
      <p className="mt-1 text-sm text-slate-500">
        Writes directly to the @@TABLE@@ table.
      </p>

      <div className="mt-5 space-y-4">
@@FORM_FIELDS_TSX@@
      </div>

      <button
        type="submit"
        disabled={busy}
        className="mt-6 w-full rounded-lg px-4 py-2.5 text-sm font-medium text-white transition disabled:opacity-60"
        style={{ background: "var(--accent)" }}
      >
        {busy ? "Saving…" : "Save @@ENTITY@@"}
      </button>

      {msg && <p className="mt-3 text-sm text-slate-600">{msg}</p>}
    </form>
  );
}
"""

ENTRY_LIST = """"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase, TABLE, isConfigured, type Row } from "@/lib/supabase";

export default function EntryList() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!isConfigured) {
      setLoading(false);
      return;
    }
    setLoading(true);
    const { data, error } = await supabase()
      .from(TABLE)
      .select("*")
      .order("created_at", { ascending: false })
      .limit(50);
    if (error) setErr(error.message);
    else {
      setErr(null);
      setRows((data ?? []) as Row[]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
    const h = () => load();
    window.addEventListener("entry:created", h);
    return () => window.removeEventListener("entry:created", h);
  }, [load]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">
          Recent @@ENTITY_PLURAL@@
        </h2>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
          {rows.length}
        </span>
      </div>

      {err && (
        <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{err}</p>
      )}

      {loading && <p className="mt-4 text-sm text-slate-500">Loading…</p>}

      {!loading && rows.length === 0 && (
        <p className="mt-4 text-sm text-slate-500">
          Nothing yet. Add your first @@ENTITY@@ on the left.
        </p>
      )}

      <ul className="mt-4 divide-y divide-slate-100">
        {rows.map((row) => (
          <li key={row.id} className="grid gap-3 py-4 sm:grid-cols-3">
@@LIST_COLUMNS_TSX@@
          </li>
        ))}
      </ul>
    </div>
  );
}
"""

STAT_BAR = """"use client";

export default function StatBar({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
    </div>
  );
}
"""

README = """# @@TITLE@@

**@@TAGLINE@@**

@@DESCRIPTION@@

A full-stack demo built with **Next.js 14 (App Router)**, **Tailwind CSS** and a
**Supabase (Postgres)** backend. Records are written from the browser straight to
Postgres through row-level security policies — no custom API layer to maintain.

---

## Stack

| Layer | Choice |
| --- | --- |
| Framework | Next.js 14, App Router, TypeScript |
| Styling | Tailwind CSS |
| Database | Supabase Postgres, RLS-secured |
| Hosting | Netlify (`@netlify/plugin-nextjs`) |

## Run it locally

```bash
npm install
cp .env.example .env.local   # add your Supabase URL + anon key
npm run dev
```

Open http://localhost:3000.

## Set up the database

Run `supabase/migrations/0001_init.sql` in the Supabase SQL editor. It is
idempotent — safe to run more than once. It creates the `@@TABLE@@` table,
enables row-level security, adds read/insert policies for anonymous users, and
seeds a few example rows.

## Data model

Table: `@@TABLE@@`

| Column | Type |
| --- | --- |
@@COLUMN_TABLE@@

Every row also has `id uuid` and `created_at timestamptz`.

## Deploy

Push to GitHub, then import the repo on Netlify. Set `NEXT_PUBLIC_SUPABASE_URL`
and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in Netlify's environment variables — the
included `netlify.toml` handles the build.

## What it does

@@FEATURE_BULLETS@@

## License

MIT
"""


def column_table(spec: dict) -> str:
    rows = [f"| `{f['name']}` | {sql_type(f)} |" for f in spec["table"]["fields"]]
    rows.append("| `created_at` | timestamptz |")
    return "\n".join(rows)


def feature_bullets(spec: dict) -> str:
    return "\n".join(f"- **{f['title']}** — {f['body']}" for f in spec.get("features", []))


def main():
    spec_path = Path(sys.argv[1])
    out = Path(sys.argv[2])
    spec = json.loads(spec_path.read_text())
    build(spec, out)

    # patch README with generated tables
    readme = (out / "README.md").read_text()
    readme = readme.replace("@@COLUMN_TABLE@@", column_table(spec))
    readme = readme.replace("@@FEATURE_BULLETS@@", feature_bullets(spec))
    (out / "README.md").write_text(readme)

    print(f"generated {out} ({len(list(out.rglob('*')))} paths)")


if __name__ == "__main__":
    main()
