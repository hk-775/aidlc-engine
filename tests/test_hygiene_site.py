from __future__ import annotations

import contextlib
import io
import json
import tomllib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from tests.support import ROOT, WorkspaceTestCase
from tools.repo_scan import (
    REQUIRED_FILES,
    decoded_provenance_terms,
    main as repo_scan_main,
    run_scans,
    scan_credentials,
    scan_denylist,
    scan_external_assets,
    scan_formatting,
    scan_python_syntax,
    scan_workflows,
)


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.tags.append((tag, dict(attrs)))


class RepositoryHygieneTests(WorkspaceTestCase):
    def test_complete_repository_scan_passes(self) -> None:
        result = run_scans(ROOT)
        self.assertTrue(result["ok"], result["findings"])
        self.assertEqual(result["scan_count"], 9)

    def test_repository_scan_cli_allows_empty_selection(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            return_code = repo_scan_main([])
        self.assertEqual(return_code, 0)
        self.assertEqual(json.loads(output.getvalue())["scan_count"], 9)

    def test_repository_scan_cli_rejects_unknown_selection(self) -> None:
        error = io.StringIO()
        with (
            contextlib.redirect_stderr(error),
            self.assertRaisesRegex(SystemExit, "2"),
        ):
            repo_scan_main(["not-a-scan"])
        self.assertIn("unknown scan selection", error.getvalue())

    def test_provenance_denylist_detects_runtime_decoded_term(self) -> None:
        root = self.workspace / "denylist"
        root.mkdir()
        term = decoded_provenance_terms()[0]
        (root / "sample.txt").write_text(f"blocked: {term}\n", encoding="utf-8")
        findings = scan_denylist(root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].scan, "denylist")

    def test_provenance_denylist_is_case_insensitive_for_personal_marker(self) -> None:
        root = self.workspace / "personal-marker"
        root.mkdir()
        term = decoded_provenance_terms()[-1].upper()
        (root / "sample.txt").write_text(f"blocked: {term}\n", encoding="utf-8")
        findings = scan_denylist(root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].scan, "denylist")

    def test_credential_scan_detects_synthetic_access_key_shape(self) -> None:
        root = self.workspace / "credentials"
        root.mkdir()
        prefix = "AK" + "IA"
        fake_value = prefix + ("A" * 16)
        (root / "sample.txt").write_text(fake_value + "\n", encoding="utf-8")
        findings = scan_credentials(root)
        self.assertEqual(len(findings), 1)

    def test_external_asset_scan_detects_network_script(self) -> None:
        root = self.workspace / "external"
        site = root / "site"
        site.mkdir(parents=True)
        remote = "https:" + "//example.invalid/app.js"
        (site / "index.html").write_text(
            f'<script src="{remote}"></script>\n',
            encoding="utf-8",
        )
        findings = scan_external_assets(root)
        self.assertEqual(len(findings), 1)

    def test_external_asset_scan_allows_navigational_links(self) -> None:
        root = self.workspace / "external-navigation"
        site = root / "site"
        site.mkdir(parents=True)
        remote = "https:" + "//example.invalid/project"
        (site / "index.html").write_text(
            f'<a href="{remote}">Repository</a>\n',
            encoding="utf-8",
        )
        self.assertEqual(scan_external_assets(root), [])

    def test_workflow_scan_detects_unpinned_action(self) -> None:
        root = self.workspace / "workflow"
        workflows = root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "bad.yml").write_text(
            "\n".join(
                (
                    "name: Bad workflow",
                    "on: workflow_dispatch",
                    "permissions:",
                    "  contents: read",
                    "jobs:",
                    "  test:",
                    "    runs-on: ubuntu-24.04",
                    "    steps:",
                    "      - uses: actions/checkout@v4",
                    "        with:",
                    "          persist-credentials: false",
                    "",
                )
            ),
            encoding="utf-8",
        )
        findings = scan_workflows(root)
        self.assertTrue(
            any("not pinned to a full commit" in finding.message for finding in findings)
        )

    def test_formatting_scan_detects_trailing_whitespace(self) -> None:
        root = self.workspace / "formatting"
        root.mkdir()
        (root / "sample.md").write_text("bad line \n", encoding="utf-8")
        findings = scan_formatting(root)
        self.assertEqual(findings[0].message, "trailing whitespace")

    def test_formatting_scan_detects_extra_eof_blank_line(self) -> None:
        root = self.workspace / "eof-formatting"
        root.mkdir()
        (root / "sample.md").write_text("content\n\n", encoding="utf-8")
        findings = scan_formatting(root)
        self.assertEqual(findings[0].message, "extra blank line at end of file")

    def test_formatting_scan_skips_binary_assets(self) -> None:
        root = self.workspace / "binary-formatting"
        root.mkdir()
        (root / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff")
        self.assertEqual(scan_formatting(root), [])

    def test_python_syntax_scan_detects_invalid_source(self) -> None:
        root = self.workspace / "syntax"
        root.mkdir()
        (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        findings = scan_python_syntax(root)
        self.assertEqual(len(findings), 1)

    def test_required_open_source_artifacts_exist(self) -> None:
        missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
        self.assertEqual(missing, [])

    def test_no_permanent_package_archives_exist(self) -> None:
        archives = [
            path
            for path in ROOT.rglob("*")
            if path.is_file()
            and ".tmp" not in path.parts
            and (
                path.suffix in {".whl", ".zip"}
                or path.name.endswith(".tar.gz")
            )
        ]
        self.assertEqual(archives, [])

    def test_lock_manifest_has_no_runtime_entries(self) -> None:
        lines = [
            line
            for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(lines, [])

    def test_build_toolchain_lock_is_hashed_and_exact(self) -> None:
        text = (ROOT / "requirements-build.lock").read_text(encoding="utf-8")
        for requirement in (
            "build==1.3.0",
            "coverage==7.13.4",
            "packaging==26.3",
            "pyproject-hooks==1.2.0",
            "setuptools==84.0.0",
            "wheel==0.48.0",
        ):
            self.assertIn(requirement, text)
        self.assertGreaterEqual(text.count("--hash=sha256:"), 12)

        pyproject = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            pyproject["build-system"]["requires"],
            ["setuptools==84.0.0"],
        )

    def test_uv_is_the_primary_installation_path(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        quickstart = (ROOT / "QUICKSTART.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("uv tool install .", readme)
        self.assertIn("uv tool install .", quickstart)
        self.assertIn("uv pip install --require-hashes", contributing)
        self.assertNotIn("PYTHONPATH=src python3 -m aidlc_engine", quickstart)

    def test_publication_inventory_covers_customer_facing_artifacts(self) -> None:
        inventory = (ROOT / "docs" / "PUBLICATION_ARTIFACTS.md").read_text(
            encoding="utf-8"
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for path in (
            "site/index.html",
            "site/architecture.html",
            "site/assets/architecture.drawio",
            "site/assets/architecture.png",
            "docs/ARCHITECTURE.md",
            "docs/PRODUCTION_READINESS.md",
            "launch-materials.md",
        ):
            with self.subTest(path=path):
                self.assertIn(path, inventory)
        self.assertIn("Architecture explorer", readme)
        self.assertIn("See it in 60 seconds", readme)
        self.assertIn("The three layers", readme)

    def test_pages_deployment_is_manual_main_only_and_permission_scoped(self) -> None:
        text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )
        trigger_block, jobs_block = text.split("jobs:", 1)
        self.assertNotIn("\n  push:", trigger_block)
        self.assertNotIn("pages: write", trigger_block)
        self.assertNotIn("id-token: write", trigger_block)
        self.assertIn("github.ref == 'refs/heads/main'", jobs_block)
        self.assertIn("ref: refs/heads/main", jobs_block)
        self.assertIn("pages: write", jobs_block)
        self.assertIn("id-token: write", jobs_block)


class StaticSiteTests(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.page_text: dict[str, str] = {}
        self.page_parsers: dict[str, SiteParser] = {}
        for name in ("index.html", "architecture.html"):
            text = (ROOT / "site" / name).read_text(encoding="utf-8")
            parser = SiteParser()
            parser.feed(text)
            self.page_text[name] = text
            self.page_parsers[name] = parser
        self.index_text = self.page_text["index.html"]
        self.architecture_text = self.page_text["architecture.html"]
        self.parser = self.page_parsers["index.html"]

    def test_page_has_language_landmarks_and_heading(self) -> None:
        html_attrs = next(attrs for tag, attrs in self.parser.tags if tag == "html")
        tags = [tag for tag, _ in self.parser.tags]
        self.assertEqual(html_attrs.get("lang"), "en")
        self.assertIn("header", tags)
        self.assertIn("nav", tags)
        self.assertIn("main", tags)
        self.assertIn("footer", tags)
        self.assertIn("h1", tags)
        self.assertIn("Automate the framework. Keep authority human.", self.index_text)
        self.assertIn("AI Development Lifecycle automation", self.index_text)

    def test_skip_link_targets_main_content(self) -> None:
        anchors = [attrs for tag, attrs in self.parser.tags if tag == "a"]
        self.assertTrue(any(attrs.get("href") == "#main" for attrs in anchors))
        main = next(attrs for tag, attrs in self.parser.tags if tag == "main")
        self.assertEqual(main.get("id"), "main")

    def test_every_image_has_nonempty_alt_text(self) -> None:
        for page_name, parser in self.page_parsers.items():
            with self.subTest(page=page_name):
                images = [attrs for tag, attrs in parser.tags if tag == "img"]
                self.assertGreaterEqual(len(images), 1)
                self.assertTrue(all(attrs.get("alt") for attrs in images))

    def test_content_policy_disables_network_connections(self) -> None:
        for page_name, parser in self.page_parsers.items():
            with self.subTest(page=page_name):
                metas = [attrs for tag, attrs in parser.tags if tag == "meta"]
                policy = next(
                    attrs["content"]
                    for attrs in metas
                    if attrs.get("http-equiv") == "Content-Security-Policy"
                )
                self.assertIn("connect-src 'none'", policy)
                self.assertIn("object-src 'none'", policy)

    def test_all_referenced_site_assets_exist(self) -> None:
        for page_name, parser in self.page_parsers.items():
            referenced = []
            for tag, attrs in parser.tags:
                if tag in {"img", "script"} and attrs.get("src"):
                    referenced.append(attrs["src"])
                relations = set((attrs.get("rel") or "").split())
                if (
                    tag == "link"
                    and relations
                    & {"icon", "manifest", "modulepreload", "preload", "stylesheet"}
                    and attrs.get("href")
                ):
                    referenced.append(attrs["href"])
            for reference in referenced:
                with self.subTest(page=page_name, reference=reference):
                    self.assertTrue((ROOT / "site" / str(reference)).is_file())

    def test_canonical_and_repository_links_are_configured(self) -> None:
        links = [attrs for tag, attrs in self.parser.tags if tag == "link"]
        canonical = next(
            attrs for attrs in links if "canonical" in (attrs.get("rel") or "").split()
        )
        self.assertEqual(canonical.get("href"), "https://hk-775.github.io/aidlc-engine/")
        architecture_links = [
            attrs
            for tag, attrs in self.page_parsers["architecture.html"].tags
            if tag == "link"
        ]
        architecture_canonical = next(
            attrs
            for attrs in architecture_links
            if "canonical" in (attrs.get("rel") or "").split()
        )
        self.assertEqual(
            architecture_canonical.get("href"),
            "https://hk-775.github.io/aidlc-engine/architecture.html",
        )
        anchors = [attrs for tag, attrs in self.parser.tags if tag == "a"]
        self.assertTrue(
            any(
                attrs.get("href") == "https://github.com/hk-775/aidlc-engine"
                for attrs in anchors
            )
        )

    def test_javascript_uses_safe_text_rendering(self) -> None:
        for name in ("app.js", "architecture.js"):
            with self.subTest(name=name):
                script = (ROOT / "site" / name).read_text(encoding="utf-8")
                self.assertNotIn("innerHTML", script)
                self.assertIn("textContent", script)
                self.assertNotIn("fetch(", script)

    def test_architecture_explorer_has_interactive_and_downloadable_artifacts(
        self,
    ) -> None:
        self.assertIn("Interactive architecture", self.architecture_text)
        self.assertIn('id="architecture-steps"', self.architecture_text)
        self.assertIn("assets/architecture.drawio", self.architecture_text)
        self.assertIn("assets/architecture.png", self.architecture_text)
        self.assertIn("assets/architecture.svg", self.architecture_text)
        self.assertIn("assets/architecture.dot", self.architecture_text)
        self.assertIn(
            "assets/aws-reference-architecture.drawio", self.architecture_text
        )
        self.assertIn(
            "assets/aws-reference-architecture.png", self.architecture_text
        )
        script = (ROOT / "site" / "architecture.js").read_text(encoding="utf-8")
        for marker in (
            'lifecycle: Object.freeze({',
            'governance: Object.freeze({',
            'persistence: Object.freeze({',
            "window.setInterval",
        ):
            self.assertIn(marker, script)

    def test_svg_assets_are_well_formed_and_described(self) -> None:
        for name in ("aidlc-engine-logo.svg", "aidlc-engine-icon.svg", "architecture.svg"):
            with self.subTest(name=name):
                root = ET.parse(ROOT / "site" / "assets" / name).getroot()
                children = list(root)
                local_names = {child.tag.rsplit("}", 1)[-1] for child in children}
                self.assertIn("title", local_names)
                self.assertIn("desc", local_names)

    def test_architecture_sources_and_rendered_assets_are_present(self) -> None:
        dot_source = (ROOT / "site" / "assets" / "architecture.dot").read_text(
            encoding="utf-8"
        )
        drawio_root = ET.parse(
            ROOT / "site" / "assets" / "architecture.drawio"
        ).getroot()
        drawio_values = " ".join(
            element.attrib.get("value", "") for element in drawio_root.iter()
        )
        svg = (ROOT / "site" / "assets" / "architecture.svg").read_text(
            encoding="utf-8"
        )
        png = (ROOT / "site" / "assets" / "architecture.png").read_bytes()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(drawio_root.tag, "mxfile")
        self.assertIn("Lifecycle core", dot_source)
        self.assertIn("Lifecycle core", drawio_values)
        self.assertIn("CI/CD + AWS deployment", drawio_values)
        self.assertIn("Lifecycle core", svg)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(png[12:16], b"IHDR")
        self.assertGreaterEqual(int.from_bytes(png[16:20], "big"), 1600)
        self.assertGreaterEqual(int.from_bytes(png[20:24], "big"), 900)
        self.assertIn(
            "site/assets/architecture.png",
            readme,
        )
        self.assertIn(
            "site/assets/architecture.drawio",
            readme,
        )

        aws_drawio_root = ET.parse(
            ROOT / "site" / "assets" / "aws-reference-architecture.drawio"
        ).getroot()
        aws_drawio_values = " ".join(
            element.attrib.get("value", "") for element in aws_drawio_root.iter()
        )
        aws_png = (
            ROOT / "site" / "assets" / "aws-reference-architecture.png"
        ).read_bytes()
        self.assertEqual(aws_drawio_root.tag, "mxfile")
        for marker in (
            "AWS reference deployment",
            "API Gateway",
            "DynamoDB",
            "AWS KMS",
            "NO EXECUTION PATH",
        ):
            self.assertIn(marker, aws_drawio_values)
        self.assertEqual(aws_png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(aws_png[12:16], b"IHDR")
        self.assertGreaterEqual(int.from_bytes(aws_png[16:20], "big"), 1600)
        self.assertGreaterEqual(int.from_bytes(aws_png[20:24], "big"), 900)
        self.assertIn("site/assets/aws-reference-architecture.png", readme)
        self.assertIn("site/assets/aws-reference-architecture.drawio", readme)

    def test_static_demo_counts_match_executable_demo(self) -> None:
        script = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        self.assertIn("auditEvents: 32", script)
        self.assertIn('currentStage: "release"', script)
