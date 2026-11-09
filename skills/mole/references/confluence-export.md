# Draw.io and Confluence

`finish` writes Markdown, offline HTML and `confluence/workflows.drawio` by
default. Use `--format markdown` for Markdown alone; repeat `--format` to select
HTML, drawio or Mermaid in addition. Markdown is always included. Mermaid is a
lossy flow representation, with limitations recorded in comments.

The uncompressed draw.io file contains one page per view and stable semantic
cell/page IDs. Shapes use plain-text labels. Internal page links use
`data:page/id,<pageId>`; no external source content is uploaded or hosted.
Source evidence and full limitations remain in Markdown/HTML sidecars.
The layout condenses cycles and places flow dependencies in columns. Shared
row gaps carry connectors, without reserving one full top lane per edge.
Draw.io preserves routing waypoints and conditional labels. Dense graphs may
still have crossings; bounded detail views and zoom remain necessary. HTML
truncates long connector text with a full tooltip/details value. Each generation
includes `export-losses.json`; browser-local edits are not applied to draw.io.

To use Confluence Cloud, install/configure a compatible draw.io app through
your organization's process, import the local file into its macro, enable
links, and disable Simple Viewer when interactive navigation is needed.
Check page links and viewer behavior on your actual tenant. The engine does
not authenticate, upload, install an app, or publish a page.

Confluence integration is NOT_RUN unless a real tenant/app test is documented.
Local XML/schema validation does not establish Confluence compatibility.

An alternative is hosting the HTML on an access-controlled HTTPS origin and
embedding it through Confluence's iFrame macro. Frame policy, authentication,
and organization approval must be checked separately. Browser-local edits stay
local; they do not become collaborative notes. MOLE does not provide hosting.

References checked during development:
- [Official XML generation and XSD](https://www.drawio.com/docs/reference/diagram-generation/)
- [Official file format and page links](https://github.com/jgraph/drawio/wiki/File-Format)
- [Interactive layers and custom links](https://www.drawio.com/docs/tutorials/interactive-diagram-layers/)
