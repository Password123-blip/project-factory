#!/usr/bin/env python3
"""Make a generated app deployable to GitHub Pages.

`generate.py` in this repo has, at times, shipped without the Pages pieces. This
script idempotently adds the two things the runbook's step 8/9 needs:

  1. .github/workflows/deploy-pages.yml  (build static export, publish to Pages)
  2. Pages-aware next.config.js          (output: "export" + basePath when
                                          GITHUB_PAGES=1)

Usage: python3 tools/pages_setup.py builds/<slug>
Safe to run more than once; it rewrites only what is missing.
"""
import sys
from pathlib import Path

WORKFLOW = """name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm install --no-audit --no-fund
      - run: npm run build
        env:
          GITHUB_PAGES: "1"
          NEXT_PUBLIC_BASE_PATH: /${{ github.event.repository.name }}
          NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
          NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: out

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
"""

CONFIG = """/** @type {import('next').NextConfig} */
const isPages = process.env.GITHUB_PAGES === "1";

const nextConfig = {
  reactStrictMode: true,
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
  ...(isPages
    ? {
        output: "export",
        images: { unoptimized: true },
        basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
        assetPrefix: process.env.NEXT_PUBLIC_BASE_PATH || "",
      }
    : {}),
};

module.exports = nextConfig;
"""


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    if not (out / "package.json").exists():
        print(f"{out} does not look like a generated app")
        return 1

    wf = out / ".github/workflows/deploy-pages.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text(WORKFLOW, encoding="utf-8")

    cfg = out / "next.config.js"
    cfg.write_text(CONFIG, encoding="utf-8")

    print(f"pages setup applied to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
