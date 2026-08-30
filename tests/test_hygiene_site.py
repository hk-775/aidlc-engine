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
        self.index_text = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
        self.parser = SiteParser()
        self.parser.feed(self.index_text)

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
        images = [attrs for tag, attrs in self.parser.tags if tag == "img"]
        self.assertGreaterEqual(len(images), 2)
        self.assertTrue(all(attrs.get("alt") for attrs in images))

    def test_content_policy_disables_network_connections(self) -> None:
        metas = [attrs for tag, attrs in self.parser.tags if tag == "meta"]
        policy = next(
            attrs["content"]
            for attrs in metas
            if attrs.get("http-equiv") == "Content-Security-Policy"
        )
        self.assertIn("connect-src 'none'", policy)
        self.assertIn("object-src 'none'", policy)

    def test_all_referenced_site_assets_exist(self) -> None:
        referenced = []
        for tag, attrs in self.parser.tags:
            if tag in {"img", "script"} and attrs.get("src"):
                referenced.append(attrs["src"])
            relations = set((attrs.get("rel") or "").split())
            if (
                tag == "link"
                and relations & {"icon", "manifest", "modulepreload", "preload", "stylesheet"}
                and attrs.get("href")
            ):
                referenced.append(attrs["href"])
        for reference in referenced:
            with self.subTest(reference=reference):
                self.assertTrue((ROOT / "site" / str(reference)).is_file())

    def test_canonical_and_repository_links_are_configured(self) -> None:
        links = [attrs for tag, attrs in self.parser.tags if tag == "link"]
        canonical = next(
            attrs for attrs in links if "canonical" in (attrs.get("rel") or "").split()
        )
        self.assertEqual(canonical.get("href"), "https://hk-775.github.io/aidlc-engine/")
        anchors = [attrs for tag, attrs in self.parser.tags if tag == "a"]
        self.assertTrue(
            any(
                attrs.get("href") == "https://github.com/hk-775/aidlc-engine"
                for attrs in anchors
            )
        )

    def test_javascript_uses_safe_text_rendering(self) -> None:
        script = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", script)
        self.assertIn("textContent", script)
        self.assertNotIn("fetch(", script)

    def test_svg_assets_are_well_formed_and_described(self) -> None:
        for name in ("aidlc-engine-logo.svg", "aidlc-engine-icon.svg", "architecture.svg"):
            with self.subTest(name=name):
                root = ET.parse(ROOT / "site" / "assets" / name).getroot()
                children = list(root)
                local_names = {child.tag.rsplit("}", 1)[-1] for child in children}
                self.assertIn("title", local_names)
                self.assertIn("desc", local_names)

    def test_architecture_source_and_rendered_asset_are_present(self) -> None:
        source = (ROOT / "site" / "assets" / "architecture.dot").read_text(
            encoding="utf-8"
        )
        rendered = (ROOT / "site" / "assets" / "architecture.svg").read_text(
            encoding="utf-8"
        )
        self.assertIn("Lifecycle core", source)
        self.assertIn("Lifecycle core", rendered)

    def test_static_demo_counts_match_executable_demo(self) -> None:
        script = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        self.assertIn("auditEvents: 32", script)
        self.assertIn('currentStage: "release"', script)
