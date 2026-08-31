UV ?= uv
UV_RUN := $(UV) run --locked --all-groups

.PHONY: help sync test coverage scan history-scan demo browser-check package-check check site

help:
	@echo "AI-DLC Engine developer targets:"
	@echo "  make sync          Install the complete uv-locked development environment"
	@echo "  make test          Run the standard-library test suite"
	@echo "  make coverage      Run branch coverage"
	@echo "  make scan          Run repository safety and quality scans"
	@echo "  make history-scan  Scan every reachable Git blob"
	@echo "  make demo          Run the complete deterministic demo"
	@echo "  make browser-check Exercise the exact public site in Chrome"
	@echo "  make package-check Build and inspect temporary package archives"
	@echo "  make check         Run the complete publication validation"
	@echo "  make site          Serve the static site at localhost:8000"

sync:
	$(UV) sync --locked --all-groups --python 3.12

test:
	$(UV_RUN) python -m unittest discover -s tests -v

coverage:
	$(UV_RUN) coverage erase
	$(UV_RUN) coverage run --branch -m unittest discover -s tests
	$(UV_RUN) coverage report

scan:
	$(UV_RUN) python tools/repo_scan.py --pretty

history-scan:
	$(UV_RUN) python tools/history_scan.py --pretty

demo:
	$(UV_RUN) python tools/demo_check.py

browser-check:
	$(UV_RUN) python tools/browser_check.py

package-check:
	$(UV_RUN) python tools/package_check.py

check: coverage scan history-scan demo browser-check package-check

site:
	$(UV_RUN) python -m http.server 8000 --directory site
