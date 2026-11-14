# Explorer foundation

Use the bundled renderer for normal generation. This is a template inside MOLE,
not a separate design skill and not a prompt to rebuild the page per repository.
The package is offline and self-contained.

## Reusable assets

- `assets/explorer/template.html`: navigation, process workspace and inspector.
- `assets/explorer/explorer.css`: shared colors, spacing and three text sizes.
- `assets/explorer/blocks.js`: text, buttons, titled sections, field/value lists,
  disclosures and process summaries. These create DOM text, not repository HTML.
- `assets/explorer/explorer.js`: model binding, selection, links and navigation.
- `assets/explorer/overrides.js`: existing local-edit persistence and transfer.
- `molekit/html.py`: embeds these assets and escaped JSON into one explorer.

Keep these assets together when packaging or installing. `doctor` checks the
template and blocks as required payload files. Generation needs no design skill,
network, font download, JavaScript package installation or external runtime.

## Stable presentation contract

The navigation contains process names. The workspace contains the current
process title, its diagram and zoom controls. The inspector contains the selected
step's explanation, applicable condition and outgoing steps. Process-level scope
appears when inspecting the process; it is not repeated under every step.

Supporting evidence, provenance and source links live in one inspector disclosure.
Local notes, IDs and edit controls live in another. Coverage belongs to a single
review disclosure below the diagram. Storage/conflict errors expand that notice
so they remain visible. Do not scatter duplicate status strips around the shell.

Typography has three roles: 14px body/actions/node labels, 12px secondary metadata
and connectors, 20px headings. Inherit these tokens in new blocks. Use weight
and spacing for hierarchy instead of adding sizes. Do not use decorative middle
dots, tracked uppercase labels or invented badges. Preserve literal source text.

Start at natural diagram scale for readable text; Fit is an explicit action and
shows the actual scale. Large graphs scroll locally. A single authored process
opens its process diagram initially; multiple processes open their map. Deep
links override the initial view, and Back retains the actual parent route.

## Content contract

Step descriptions are short action labels. Their claims provide the explanation,
and the generated step node retains those exact claim IDs so other claims sharing
a README or source span do not appear as its proof. Step conditions appear in the
inspector. Explicit transition labels carry branch conditions in the diagram.

Failure paths provide explanations. Include an outcome as an authored step with
explicit transitions when it must appear in the diagram; do not create a second,
disconnected failure card merely to repeat the explanation. Runtime uncertainty
and provenance remain intact even when hidden behind a disclosure.

## Verification boundary

Verify through `start`, `inspect`, `submit`, `finish`, not a hand-built preview.
Exercise process selection, subprocess opening, Back, explicit decision branches,
evidence/edits disclosures and source links. Check desktop and narrow layouts,
keyboard controls, local scrolling, actual zoom readouts, and portable edit
round-trips. A copied installed package must render without any other skill.
