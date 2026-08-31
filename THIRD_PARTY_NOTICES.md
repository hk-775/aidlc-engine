# Third-party notices

AI-DLC Engine 0.1.0 has no runtime dependencies and vendors no third-party source,
fonts, scripts, images, binaries, or generated bundles.

Development and automation environments may provide tools such as Python,
Coverage.py, a Python build frontend, Git, Make, gitleaks, and GitHub Actions.
Those tools are not bundled into the AI-DLC Engine runtime or wheel and remain
subject to their own licenses.

The canonical `uv.lock` currently resolves these direct development
dependencies:

| Package | Version | License | Purpose | Distribution status |
| --- | --- | --- | --- | --- |
| build | 1.3.0 | MIT | Create temporary source and wheel archives | Development only; package code is not bundled |
| coverage | 7.13.4 | Apache-2.0 | Measure branch coverage | Development only; package code is not bundled |
| setuptools | 84.0.0 | MIT | Build backend | Build only; package code is not bundled |
| websocket-client | 1.9.2 | Apache-2.0 | Connect the local Chrome test to the DevTools protocol | Development only; package code is not bundled |
| wheel | 0.48.0 | MIT | Build universal wheel archives | Development only; package code is not bundled |

These packages are obtained from the Python Package Index through hash-pinned
entries in `uv.lock`. Transitive development dependencies remain governed by
their upstream licenses and are likewise not bundled.

The Apache License 2.0 text in `LICENSE` is the standard license grant for this
project.

Before adding a dependency or copied asset, contributors must document its
name, version, source, license, purpose, and distribution status here.
