# Diagram engine validation

The current Systems diagrams remain fixed by default so the approved visual composition does not regress.

To compare the automatic engine locally, start the portfolio and add `?diagramEngine=auto` to the URL.

```bash
pnpm dev
```

Default approved rendering:

```text
http://localhost:5173/
```

Automatic engine:

```text
http://localhost:5173/?diagramEngine=auto
```

Validate at 1440, 1024, 768, 680, 425, 375 and 320 px. The automatic renderer uses a layered left-to-right layout on desktop when the graph fits and a layered top-to-bottom layout on mobile. Backward narrative edges are treated as feedback and routed separately.

The engine is not production-default yet. Promotion requires visual approval of all seven Systems projects.
