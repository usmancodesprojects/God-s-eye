# Verification notes

## Automated checks

- Frontend: 8 Node tests passed, covering all supplied instances and method selections, derived zone coverage, non-contiguous ID lookup, polygon closure, bad references and invalid bounding boxes.
- Backend: 10 unittest cases passed using the pinned requirements, covering byte-equivalent JSON content after API serialization, all supplied summary totals, live argument forwarding, default bounds, missing adapter, invalid parameters, bad output, exceptions, concurrency and CORS.
- Vite production build completed successfully. The application includes MapLibre and Chart.js, so initial JavaScript is larger than a basic static page.

## Browser checks

Checked the saved-result UI and method switching, camera inspector, quantum diagnostics and instance selector in the supplied preview browser. Checked all three supplied instances, QAOA/Exact/Greedy summaries, camera inspection, quantum statistics/charts, and failed-request recovery. The API is not reachable from the isolated browser preview; its offline error was checked without losing the active result.

The preview browser has WebGL disabled. Its 3D-context creation fails before MapLibre can initialize; the labelled 2D fallback is verified instead. Actual city tiles, building extrusion, fly-to behavior and custom 3D rays still need a smoke test in a normal WebGL2-enabled Chrome/Edge/Firefox browser. Do not treat the fallback as proof that the 3D rendering was visually tested.

## Real HTTP integration check

The built frontend was served by FastAPI in single-server mode. Real HTTP checks passed for the index page, health endpoint, all three static saved JSON files, corresponding API result endpoints, and the expected 503 response without a real solver. Static saved files use `/saved-results/` to avoid colliding with API `/results/{instance}`.

The optional `npm run dev` launcher started FastAPI but this environment prevented Vite from enumerating network interfaces when launched as a nested process. The separate frontend preview and production build succeeded. The one-command launcher should receive a local smoke test on your computer; the README also provides independent frontend/backend commands.

## Solver boundary

No real solver callable was supplied. API forwarding is tested using a test-only fake; an actual QAOA execution cannot be verified until Huzaifa connects his adapter. Saved JSON is never returned by `/optimize` as a fabricated live run.
