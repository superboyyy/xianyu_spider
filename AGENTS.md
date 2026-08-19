# AGENTS.md

## Cursor Cloud specific instructions

This repo is a single Python/FastAPI service: the 闲鱼商品搜索API (Xianyu/Goofish product
search API) in `spider.py`, which drives a headless Playwright Chromium browser to scrape
`www.goofish.com` and persists results to a database via Tortoise ORM. `test.py` is an
optional CLI that reuses the scraper to export results to Excel. Standard setup/run/test
commands live in `README.md`; only the non-obvious caveats are below.

- Python is available only as `python3` (3.12); there is no `python` symlink. The README
  shows `python spider.py` / `python test.py` — use `python3` instead.
- pip installs into the user site (`~/.local`), so console-script shims like `pytest`,
  `uvicorn`, and `playwright` are NOT on `PATH`. Invoke them as modules:
  `python3 -m pytest`, `python3 -m playwright ...`, `python3 spider.py`.
- Live search needs the Playwright Chromium browser (installed by the update script) AND
  outbound network access to `www.goofish.com`. The scraper is subject to Xianyu anti-bot
  measures (login popups, `RGV587`/slider captcha), so an occasional run may return few or
  zero results even though the setup is correct — retry rather than assuming breakage.
- The database defaults to SQLite at `./xianyu.db` (gitignored) and its schema is
  auto-created on startup (`generate_schemas=True`); there are no migrations to run. Set
  `DATABASE_URL` (e.g. in `.env`) to use MySQL instead.
- Run the server with `python3 spider.py` (listens on `0.0.0.0:8000`); interactive docs are
  at `http://localhost:8000/docs`. `GET /health` and the unit tests need neither Chromium
  nor network access; only `POST /search/` does.
