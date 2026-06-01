# Structural Overview: How This Project Customizes Lektor

This note describes the *structural* customizations layered on top of a vanilla
[Lektor](https://www.getlektor.com) project, for a reader who is already familiar
with Lektor's core concepts (project file, models, content tree, templates,
plugins, databags). It maps each customization to the Lektor extension point it
uses and links the relevant Lektor documentation. For installation and deployment
mechanics see the [README](../README.md); for a quick local build see
[Local development](#local-development) below.

At a high level, the site is a fairly ordinary Lektor static site with four
non-trivial additions:

1. A **custom plugin** (`conference-template-functions`) that adds Jinja globals/
   filters and a Markdown link mixin.
2. **CSV files used as page-scoped databases** (papers, schedule, sponsors),
   attached to content pages and parsed at render time by the plugin.
3. A **static databag** (`drivepaths.json`) that maps logical paper paths to
   Google Drive file IDs, decoupling the site from the Drive API at build time.
4. A **Gulp/Sass/Rollup front-end pipeline** feeding Lektor's `assets/` directory.

Notably, the project deliberately uses **no flow blocks**
([Flow](https://www.getlektor.com/docs/models/flow/)) — structured, repeating
content (papers, schedule rows, sponsors) is expressed as CSV attachments instead
of Lektor flow content.

---

## 1. Project file & deployment

Docs: [Project File](https://www.getlektor.com/docs/project/) ·
[Deployment](https://www.getlektor.com/docs/deployment/) ·
[GitHub Pages](https://www.getlektor.com/docs/deployment/ghpages/)

[`ATMSeminar.lektorproject`](../ATMSeminar.lektorproject) is intentionally minimal:
it sets the project `name` and defines a single `ghpages://` deploy server with a
`cname` query argument for the custom domain. Note that the plugin is **not**
declared here — it lives in `packages/` (see §3) and is installed via
`lektor plugins reinstall`, which is the documented way to use a locally-developed
plugin rather than a published one.

Deployment uses Lektor's built-in GitHub Pages publisher (the
`ghpages://owner/repo?cname=...` target). CI/CD wraps the same commands: a push to
the `production` branch triggers a GitHub Actions workflow under
[`.github/workflows/`](../.github/) that runs `lektor plugins reinstall` →
`lektor build` → `lektor deploy ghpages`. The repo also carries a legacy
[`.gitlab-ci.yml`](../.gitlab-ci.yml) from an earlier GitLab Pages setup; it is no
longer the active pipeline.

---

## 2. Data models

Docs: [Models](https://www.getlektor.com/docs/models/)

The [`models/`](../models/) directory defines seven models. They use standard
Lektor model features (field types, `[model]` headers, and model inheritance via
`inherits =`):

| Model | Inherits | Notable fields | Purpose |
|---|---|---|---|
| `page` | — | `title`, `breadcrumb_name`, `body` (markdown), `additional_sponsors` (html) | Generic content page |
| `homepage` | — | `title`, `body`, `breadcrumb_name`, `next_location` | Site / section landing pages |
| `gallery` | `page` | (none added) | Image gallery pages |
| `pastseminar` | `page` | `start_date`, `end_date`, `short_menu_name` | A past seminar/symposium edition |
| `papers_gen` | — | `content_url_prefix`, `presentation_format` | Paper/presentation listing page |
| `papers` | — | `title`, `body` | Paper container page |
| `page_schedule` | — | (relies on `schedule.csv`) | Schedule page |

Two model patterns are worth calling out:

- **`short_menu_name` (on `pastseminar`)** is an optional label override read by the
  navigation template, added so menu labels can diverge from the auto-computed
  formula. The rationale and template change are documented in
  [`issues_encountered/20251127_navigation_menu_fix.md`](./issues_encountered/20251127_navigation_menu_fix.md).
- **The listing/schedule models carry almost no fields.** The actual tabular data
  lives in CSV attachments (§4), not in model fields — these models exist mainly to
  bind a content page to its specialized template.

---

## 3. Custom plugin: `conference-template-functions`

Docs: [Plugins](https://www.getlektor.com/docs/plugins/) ·
[Writing plugins](https://www.getlektor.com/docs/plugins/howto/) ·
[Environment API](https://www.getlektor.com/docs/api/environment/)

The plugin lives in
[`packages/conference-template-functions/`](../packages/conference-template-functions/)
(class `ConferenceTemplatePlugin`, v0.1.6) and is installed into the active
environment with `lektor plugins reinstall`. It uses two plugin hooks:

### `on_setup_env` — Jinja globals, filters, and extensions

Registers a set of globals on `env.jinja_env.globals` (see
[Jinja environment](https://www.getlektor.com/docs/api/environment/jinja_env/)):

- **CSV readers** — `paper_csv(attachments, organized=False)`,
  `schedule_csv(attachments)`, `sponsors_csv(year=None)`, and generic
  `parse_csv(attachments, name)`. These read CSV attachments and return helper
  objects (`PapersTable` / `PapersTopicData` / `ScheduleData`).
- **Column predicates** — `has_papers`, `has_presentations`, `has_videos`,
  `has_best`, `has_abstracts_file`, `has_themes` — used by templates to decide
  which columns/links to render.
- **Drive URL resolver** — `get_drive_url(path)` (also registered as the `drive`
  filter; see §5).
- **Navigation helpers** — `page_reverse_order(page)` (walks `.parent` to build a
  breadcrumb trail) and `filter_breadcrumbs(pages)` (stops at a page flagged
  `skip_breadcrumbs`).
- **Presentation helpers** — `get_unique_colors(n)` (evenly-spaced HSL palette for
  category badges) and `get_attr_funct(attr)`.
- **Plain Python built-ins exposed to templates** — `enumerate`, `set`, `list`,
  `reversed`, `sorted`, `len`, `dir`, `uuid4`, and a `unicode` alias.

It also enables the `jinja2.ext.loopcontrols` extension so templates can use
`break`/`continue` inside loops.

> Per Lektor's plugin guidance this exposes more globals than the recommended
> minimum; the functions are tightly coupled to this site's content conventions.

### `on_markdown_config` — Markdown link mixin

Appends a `LinkMixin` to `config.renderer_mixins`, overriding link rendering in
Markdown bodies. The mixin:

- resolves scheme-less links relative to the current record via `record.url_to(...)`;
- treats a leading `!` as a "nofollow" marker (emits `rel="nofollow"`);
- rewrites any link containing `/seminarContent/...` to a Google Drive URL via
  `get_drive_url()` (§5).

This is what lets an author write an ordinary Markdown link to a paper path and
have it resolve to the correct Drive download link at build time.

---

## 4. CSV-as-database attachments

Docs: [Attachments](https://www.getlektor.com/docs/content/attachments/)

Rather than modeling papers, schedule rows, and sponsors as Lektor records or flow
blocks, the project stores them as **CSV files attached to the relevant content
page** (i.e. sitting next to `contents.lr`). Lektor treats these as ordinary
attachments; the plugin's CSV readers (§3) parse them with `csv.DictReader`
(UTF-8-BOM aware) at render time.

- **`papers.csv`** — on `papers_gen` listing pages. Columns include
  `id, title, authors, paper, presentation, best, theme`/`track, abstract`. The
  `paper`/`presentation` columns hold `/seminarContent/...` paths resolved to Drive
  links. When `organized=True` and a `theme`/`track` column exists, rows are grouped
  by topic (`PapersTopicData`). Sibling `keynotes.csv` / `tutorials.csv` are merged
  into ordered sections.
- **`schedule.csv`** — on `page_schedule` pages. Parsed by `ScheduleData` into a
  nested day → event → session → paper structure, with date/time parsing.
- **`sponsors.csv`** — read from the `/sponsors/` page; optionally filtered by `year`.

This keeps bulk tabular data editable as spreadsheets and out of the content/model
layer.

---

## 5. Google Drive databag (`drivepaths.json`)

Docs: [Data Bags](https://www.getlektor.com/docs/content/databags/)

Papers and presentations are hosted on Google Drive, not in the repo. The mapping
from logical path to Drive file ID is a static databag at
[`databags/drivepaths.json`](../databags/) (~270 KB), e.g.:

```json
{ "/seminarContent/seminar1/papers/p_001_CDR.pdf": "1NhASPfwbOs7UwriIQNkl2GYErphrD7ws" }
```

`get_drive_url(path)` reads it via `site_proxy.databags.get_bag('drivepaths')` and
returns `https://drive.google.com/file/d/<id>/view?usp=sharing`. If a
`/seminarContent/...` path is missing from the bag it raises `ValueError` (a missing
mapping fails the build loudly rather than producing a dead link).

**This file is not hand-maintained.** It is generated by
[pydrivelist](https://github.com/atmseminar-org/pydrivelist) — a small utility
created specifically for this project that walks the conference's Google Drive
folder and emits the path → file-ID mapping, which is then committed to the repo.
Regenerating it requires access to that Drive folder (you must be added as a user),
and the rendered download links are only as current as the committed `drivepaths.json`.
Using a static databag deliberately keeps the build offline and free of Drive API
calls.

---

## 6. Templates

Docs: [Templates](https://www.getlektor.com/docs/templates/)

The [`templates/`](../templates/) directory uses standard Lektor/Jinja inheritance
(`layout.html` as the base; `layout-home.html` and `page.html` extend it) plus
partials/macros (`head.html`, `header.html`, `footer.html`, `navigation.html`,
`breadcrumb.html`). The site-specific behavior is concentrated in templates that
call the plugin's globals/filters:

- `papers_gen.html` + `paper_table_data.html` — call `paper_csv(...)`, the `has_*`
  predicates, `get_unique_colors(...)`, and the `drive` filter.
- `page_schedule.html` + `schedule.html` — call `schedule_csv(...)`.
- `sponsors.html` — calls `sponsors_csv(year=...)`.
- `navigation.html` — queries the content tree (`site.get('/past-seminars/')`),
  sorts children by `start_date`, and uses `short_menu_name` when present.
- `breadcrumb.html` — uses `page_reverse_order` / `filter_breadcrumbs`.

---

## 7. Front-end asset pipeline

Docs (Lektor side): [Project File / project layout](https://www.getlektor.com/docs/project/)

The CSS/JS build is **outside** Lektor: [`gulpfile.js`](../gulpfile.js) +
[`package.json`](../package.json) define a Gulp 4 pipeline that compiles Sass →
CSS, bundles JS with Rollup + Babel + Uglify, copies vendor libraries (Bootstrap 5,
Swiper, Lottie, etc.), and runs a browser-sync watch task. Its outputs land in
[`assets/static/`](../assets/), which is Lektor's standard static-asset directory —
Lektor then copies `assets/` into the generated site under `build/static/`. In
other words, Gulp owns compilation; Lektor owns publishing the compiled result.

---

## Summary: customization → Lektor extension point

| Customization | Lektor extension point | Key files |
|---|---|---|
| Minimal project + ghpages deploy | Project file / GitHub Pages publisher | `ATMSeminar.lektorproject`, `.github/workflows/` |
| Page types & menu label override | Models (+ inheritance) | `models/*.ini` |
| Jinja globals/filters, loop controls | Plugin `on_setup_env` | `packages/conference-template-functions/` |
| Drive link rewriting in Markdown | Plugin `on_markdown_config` (renderer mixin) | `packages/.../conference_template_functions.py` |
| Papers / schedule / sponsors data | Attachments (CSV) | `content/**/papers.csv`, `schedule.csv`, `sponsors.csv` |
| Path → Drive ID mapping | Databag (static) | `databags/drivepaths.json` (via `pydrivelist`) |
| Specialized rendering | Templates (inheritance + plugin functions) | `templates/*.html` |
| CSS/JS build | (external) feeding Lektor `assets/` | `gulpfile.js`, `package.json`, `assets/static/` |

---

## Local development

Install Lektor into a Python virtualenv, then install the bundled plugin and build:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install lektor
# from this project root:
lektor plugins reinstall   # installs conference-template-functions from packages/
lektor build               # full static build (or: lektor server)
```

A clean `lektor build` confirms the model / plugin / databag / attachment wiring
described above. This has been verified with **Lektor 3.3.x** on **Python 3.13**
(which emits a harmless `pkg_resources is deprecated` warning); the project's CI
pins Python 3.10.
