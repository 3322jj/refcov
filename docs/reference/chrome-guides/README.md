# Chrome modern web guidance (selected guides)

These files are copied unchanged from the `guides/` folder of the `modern-web-guidance` package, version 1.0.0, published by the Chrome team under the Apache License 2.0 (see `LICENSE` in this folder).

They are reference material for the demo page in `site/`: RefCov is configured so that the page's code is written only after these guides have been read (`.kiro/specs/demo-page/requirements.md`, requirement 16).

## How the guides were chosen

Not by hand. Each requirement of the demo page that concerns how the page is built was turned into one short English query, run through the package's own search command (`modern-web.mjs search`), and the top 3 results of every query were kept, without adding or removing any. This is the same rule as in `docs/前端扩展试验结果.md`. Some results are only loosely related to the page; they are kept anyway, because the rule is the point.

| Requirement | Query | Top 3 results |
|---|---|---|
| 13.1 | `follow system color scheme` | `dark-mode-toggle`, `color`, `component-specific-light-dark-theme` |
| 13.2 | `responsive layout small screens` | `css-layout`, `responsive-design`, `responsive-table` |
| 13.3 | `visible keyboard focus` | `accessibility`, `2d-panning`, `natural-interactions` |
| 13.4 | `text color contrast` | `contrast-color`, `color`, `highlight-text-ranges` |
| 13.5 | `screen reader status of grid cells` | `responsive-table`, `accessibility`, `tabs` |
| 13.6 | `reduce motion animations` | `motion`, `dynamic-sibling-animations`, `scrollytelling` |
| 3 | `accessible data table` | `responsive-table`, `accessibility`, `sortable-table` |
| 1.3, 2.3 | `animate grid cells one by one` | `css-layout`, `tabs`, `card` |

17 guides in total. Selected by Claude on 2026-11-17; registered by the user with `refcov add`.
