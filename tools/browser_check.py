#!/usr/bin/env python3
"""Exercise the exact AI-DLC Engine public site in Chrome."""

from __future__ import annotations

import argparse
import base64
import contextlib
import http.server
import json
import mimetypes
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterator

import websocket

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SITE_ROOT = ROOT / "site"
DEFAULT_BASE_PATH = "/aidlc-engine/"
EXPECTED_ASSETS = (
    "",
    "index.html",
    "architecture.html",
    "styles.css",
    "app.js",
    "architecture.js",
    "assets/aidlc-engine-icon.svg",
    "assets/aidlc-engine-logo.svg",
    "assets/architecture.dot",
    "assets/architecture.drawio",
    "assets/architecture.png",
    "assets/architecture.svg",
    "assets/aws-reference-architecture.drawio",
    "assets/aws-reference-architecture.png",
)


class BrowserCheckError(RuntimeError):
    """Raised when the public site fails deterministic browser verification."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BrowserCheckError(message)


class StaticSiteHandler(http.server.BaseHTTPRequestHandler):
    """Serve one repository-owned site beneath the exact Pages base path."""

    site_root = DEFAULT_SITE_ROOT
    base_path = DEFAULT_BASE_PATH
    requests: list[dict[str, object]] = []

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(include_body=False)

    def do_GET(self) -> None:  # noqa: N802
        self._serve(include_body=True)

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def _finish(
        self,
        status: int,
        body: bytes,
        content_type: str,
        *,
        include_body: bool,
    ) -> None:
        self.requests.append(
            {
                "method": self.command,
                "path": urllib.parse.urlsplit(self.path).path,
                "status": status,
            }
        )
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _serve(self, *, include_body: bool) -> None:
        try:
            request_path = urllib.parse.unquote(
                urllib.parse.urlsplit(self.path).path
            )
            if request_path in {
                self.base_path,
                self.base_path.removesuffix("/"),
            }:
                relative_path = "index.html"
            elif request_path.startswith(self.base_path):
                relative_path = request_path[len(self.base_path) :]
            else:
                self._finish(
                    404,
                    b"Not found\n",
                    "text/plain; charset=utf-8",
                    include_body=include_body,
                )
                return

            candidate = (self.site_root / relative_path).resolve()
            if not candidate.is_relative_to(self.site_root) or not candidate.is_file():
                self._finish(
                    404,
                    b"Not found\n",
                    "text/plain; charset=utf-8",
                    include_body=include_body,
                )
                return
            body = candidate.read_bytes()
            content_type = (
                mimetypes.guess_type(candidate.name)[0]
                or "application/octet-stream"
            )
            if content_type.startswith("text/") or candidate.suffix in {
                ".dot",
                ".drawio",
                ".js",
                ".svg",
            }:
                content_type = f"{content_type}; charset=utf-8"
            self._finish(
                200,
                body,
                content_type,
                include_body=include_body,
            )
        except (OSError, UnicodeError):
            self._finish(
                500,
                b"Server error\n",
                "text/plain; charset=utf-8",
                include_body=include_body,
            )


@contextlib.contextmanager
def local_site(
    site_root: Path,
    base_path: str,
) -> Iterator[tuple[str, list[dict[str, object]]]]:
    handler = type("ConfiguredStaticSiteHandler", (StaticSiteHandler,), {})
    handler.site_root = site_root.resolve()
    handler.base_path = base_path
    handler.requests = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}{base_path}", handler.requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request_status(url: str) -> int:
    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "aidlc-engine-browser-check/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def locate_chrome() -> str:
    candidates = (
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    for command in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        candidate = shutil.which(command)
        if candidate:
            return candidate
    raise BrowserCheckError(
        "Chrome or Chromium is required; set CHROME_BIN when it is not on PATH"
    )


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request_json(url: str, *, method: str = "GET") -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "aidlc-engine-browser-check/1"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class DevTools:
    """Minimal Chrome DevTools Protocol client with event recording."""

    def __init__(self, url: str, expected_origin: str) -> None:
        self.socket = websocket.create_connection(
            url,
            timeout=10,
            origin=expected_origin,
        )
        self.next_id = 1
        self.request_urls_by_id: dict[str, str] = {}
        self.request_urls: list[str] = []
        self.responses: list[dict[str, object]] = []
        self.loading_failures: list[dict[str, object]] = []
        self.browser_exceptions: list[str] = []
        self.console_errors: list[str] = []
        self.websockets: list[str] = []

    def close(self) -> None:
        self.socket.close()

    def _record(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        params = message.get("params") or {}
        if method == "Network.requestWillBeSent":
            url = (params.get("request") or {}).get("url")
            if isinstance(url, str):
                self.request_urls.append(url)
                request_id = params.get("requestId")
                if isinstance(request_id, str):
                    self.request_urls_by_id[request_id] = url
        elif method == "Network.responseReceived":
            response = params.get("response") or {}
            url = response.get("url")
            status = response.get("status")
            if isinstance(url, str) and isinstance(status, (int, float)):
                self.responses.append({"url": url, "status": status})
        elif method == "Network.loadingFailed":
            request_id = params.get("requestId")
            self.loading_failures.append(
                {
                    "url": (
                        self.request_urls_by_id.get(request_id, "")
                        if isinstance(request_id, str)
                        else ""
                    ),
                    "error": params.get("errorText", "request failed"),
                    "blocked_reason": params.get("blockedReason", ""),
                }
            )
        elif method == "Network.webSocketCreated":
            url = params.get("url")
            if isinstance(url, str):
                self.websockets.append(url)
        elif method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails") or {}
            exception = details.get("exception") or {}
            self.browser_exceptions.append(
                exception.get("description")
                or details.get("text")
                or "unknown browser exception"
            )
        elif method == "Runtime.consoleAPICalled" and params.get("type") == "error":
            values = []
            for argument in params.get("args") or []:
                values.append(
                    str(argument.get("value") or argument.get("description") or "")
                )
            self.console_errors.append(" ".join(values))
        elif method == "Log.entryAdded":
            entry = params.get("entry") or {}
            if entry.get("level") == "error":
                self.console_errors.append(
                    str(entry.get("text") or "browser log error")
                )

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        identifier = self.next_id
        self.next_id += 1
        self.socket.send(
            json.dumps(
                {
                    "id": identifier,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        while True:
            message = json.loads(self.socket.recv())
            self._record(message)
            if message.get("id") != identifier:
                continue
            if "error" in message:
                raise BrowserCheckError(f"{method}: {message['error']}")
            return message.get("result") or {}

    def evaluate(self, expression: str) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        if result.get("exceptionDetails"):
            details = result["exceptionDetails"]
            exception = details.get("exception") or {}
            raise BrowserCheckError(
                exception.get("description")
                or details.get("text")
                or "browser evaluation failed"
            )
        return (result.get("result") or {}).get("value")

    def wait_for(
        self,
        expression: str,
        description: str,
        *,
        timeout: float = 10,
    ) -> Any:
        deadline = time.monotonic() + timeout
        last_value: Any = None
        while time.monotonic() < deadline:
            last_value = self.evaluate(expression)
            if last_value:
                return last_value
            time.sleep(0.05)
        raise BrowserCheckError(
            f"timed out waiting for {description}: {last_value!r}"
        )

    def navigate(self, url: str) -> None:
        result = self.call("Page.navigate", {"url": url})
        require(not result.get("errorText"), f"navigation failed: {result}")
        target = json.dumps(url)
        self.wait_for(
            f"document.readyState === 'complete' && location.href === {target}",
            f"{url} to finish loading",
            timeout=15,
        )

    def click(self, selector: str) -> None:
        serialized = json.dumps(selector)
        clicked = self.evaluate(
            "(() => {"
            f"const element = document.querySelector({serialized});"
            "if (!element || element.disabled) return false;"
            "element.click();"
            "return true;"
            "})()"
        )
        require(bool(clicked), f"missing or disabled control: {selector}")

    def set_mobile_viewport(self) -> None:
        self.call(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 390,
                "height": 844,
                "deviceScaleFactor": 1,
                "mobile": True,
            },
        )
        time.sleep(0.1)

    def clear_mobile_viewport(self) -> None:
        self.call("Emulation.clearDeviceMetricsOverride")

    def capture_screenshot(self, path: Path) -> None:
        result = self.call(
            "Page.captureScreenshot",
            {
                "format": "png",
                "captureBeyondViewport": False,
                "fromSurface": True,
            },
        )
        encoded = result.get("data")
        require(isinstance(encoded, str), "Chrome returned no screenshot data")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(encoded))

    def settle(self) -> None:
        time.sleep(0.15)
        self.evaluate("document.readyState === 'complete'")


@contextlib.contextmanager
def chrome_session() -> Iterator[DevTools]:
    with tempfile.TemporaryDirectory(
        prefix="aidlc-engine-chrome-",
        ignore_cleanup_errors=True,
    ) as directory:
        profile = Path(directory)
        port = free_port()
        command = [
            locate_chrome(),
            "--headless=new",
            "--disable-background-networking",
            "--disable-breakpad",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-dev-shm-usage",
            "--disable-extensions",
            "--disable-features=MediaRouter,OptimizationHints,Translate",
            "--disable-gpu",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-default-browser-check",
            "--no-first-run",
            "--remote-allow-origins=*",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={profile}",
            "--window-size=1280,900",
            "about:blank",
        ]
        if sys.platform.startswith("linux"):
            command.insert(1, "--no-sandbox")
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        browser: DevTools | None = None
        try:
            endpoint = f"http://127.0.0.1:{port}/json/version"
            deadline = time.monotonic() + 20
            version: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    break
                try:
                    version = request_json(endpoint)
                    break
                except (OSError, urllib.error.URLError, json.JSONDecodeError):
                    time.sleep(0.1)
            require(version is not None, "Chrome DevTools endpoint did not become ready")
            target = request_json(
                f"http://127.0.0.1:{port}/json/new?"
                + urllib.parse.quote("about:blank", safe=""),
                method="PUT",
            )
            browser = DevTools(
                target["webSocketDebuggerUrl"],
                f"http://127.0.0.1:{port}",
            )
            browser.call("Page.enable")
            browser.call("Runtime.enable")
            browser.call("Network.enable")
            browser.call("Network.setCacheDisabled", {"cacheDisabled": True})
            browser.call("Log.enable")
            yield browser
        finally:
            if browser is not None:
                with contextlib.suppress(OSError):
                    browser.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def normalize_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme in {"http", "https"}, "base URL must use HTTP or HTTPS")
    require(bool(parsed.netloc), "base URL must include a host")
    path = parsed.path or "/"
    if not path.endswith("/"):
        path += "/"
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, path, "", "")
    )


def assert_mobile_layout(browser: DevTools, page_name: str) -> None:
    browser.set_mobile_viewport()
    require(
        bool(
            browser.evaluate(
                "document.documentElement.scrollWidth "
                "<= document.documentElement.clientWidth + 1"
            )
        ),
        f"{page_name} overflows a 390-pixel mobile viewport",
    )


def verify_browser(
    base_url: str,
    screenshot_directory: Path | None = None,
) -> dict[str, object]:
    base_url = normalize_base_url(base_url)
    parsed_base = urllib.parse.urlsplit(base_url)
    allowed_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    base_path = parsed_base.path

    for asset in EXPECTED_ASSETS:
        url = urllib.parse.urljoin(base_url, asset)
        require(
            request_status(url) == 200,
            f"public asset did not resolve with HTTP 200: {url}",
        )

    with chrome_session() as browser:
        browser.navigate(base_url)
        browser.wait_for(
            "document.querySelectorAll('#stage-list li').length === 6",
            "the synthetic lifecycle status",
        )
        landing = browser.evaluate(
            """(() => {
              const image = document.querySelector(
                'img[src="assets/architecture.svg"]'
              );
              const architectureLink = [...document.querySelectorAll("a")]
                .find((anchor) => anchor.textContent.includes(
                  "Explore the architecture"
                ));
              return {
                title: document.title,
                pathname: document.location.pathname,
                heading: document.querySelector("h1")?.textContent.trim(),
                stageCount: document.querySelectorAll("#stage-list li").length,
                summary: document.querySelector("#stage-summary")?.textContent,
                metrics: document.querySelector("#audit-summary")?.textContent,
                imageComplete: Boolean(
                  image && image.complete && image.naturalWidth > 0
                ),
                imageUrl: image ? image.src : "",
                architectureUrl: architectureLink ? architectureLink.href : "",
                rootRelativeCount: [...document.querySelectorAll("a")]
                  .filter((anchor) => anchor.getAttribute("href")?.startsWith("/"))
                  .length,
              };
            })()"""
        )
        require(
            landing["title"]
            == "AI-DLC Engine | Human-governed lifecycle automation",
            "landing page title is incorrect",
        )
        require(
            landing["pathname"] == base_path,
            "landing page did not retain the exact project base path",
        )
        require(
            landing["heading"] == "Automate the framework. Keep authority human.",
            "landing page heading is missing",
        )
        require(landing["stageCount"] == 6, "synthetic lifecycle stages did not render")
        require(
            landing["summary"]
            == "Civic Forms Pilot reached the release stage after human approval.",
            "synthetic lifecycle summary did not render",
        )
        require(
            "Audit events" in landing["metrics"]
            and "32" in landing["metrics"]
            and "valid" in landing["metrics"],
            "synthetic audit metrics did not render",
        )
        require(landing["imageComplete"], "landing architecture image did not load")
        require(
            urllib.parse.urlsplit(landing["imageUrl"]).path
            == f"{base_path}assets/architecture.svg",
            "landing architecture image resolved outside the Pages base",
        )
        require(
            urllib.parse.urlsplit(landing["architectureUrl"]).path
            == f"{base_path}architecture.html",
            "landing architecture link resolved outside the Pages base",
        )
        require(
            landing["rootRelativeCount"] == 0,
            "landing page contains a root-relative link",
        )
        if screenshot_directory is not None:
            browser.capture_screenshot(screenshot_directory / "landing-desktop.png")
        assert_mobile_layout(browser, "landing page")
        if screenshot_directory is not None:
            browser.capture_screenshot(screenshot_directory / "landing-mobile.png")
        browser.clear_mobile_viewport()

        architecture_url = urllib.parse.urljoin(base_url, "architecture.html")
        browser.navigate(architecture_url)
        browser.wait_for(
            "document.querySelectorAll('#architecture-steps li').length === 6",
            "the interactive architecture steps",
        )
        architecture = browser.evaluate(
            """(() => {
              const currentImage = document.querySelector(
                'img[src="assets/architecture.png"]'
              );
              const awsImage = document.querySelector(
                'img[src="assets/aws-reference-architecture.png"]'
              );
              const downloads = [...document.querySelectorAll(
                ".download-grid a[download]"
              )].map((anchor) => anchor.href);
              return {
                title: document.title,
                pathname: document.location.pathname,
                tabCount: document.querySelectorAll("[data-scenario]").length,
                heading: document.querySelector("#scenario-title")?.textContent,
                step: document.querySelector("#step-title")?.textContent,
                currentImageComplete: Boolean(
                  currentImage
                  && currentImage.complete
                  && currentImage.naturalWidth > 0
                ),
                awsImageComplete: Boolean(
                  awsImage && awsImage.complete && awsImage.naturalWidth > 0
                ),
                rootRelativeCount: [...document.querySelectorAll("a")]
                  .filter((anchor) => anchor.getAttribute("href")?.startsWith("/"))
                  .length,
                downloads,
              };
            })()"""
        )
        require(
            architecture["title"] == "AI-DLC Engine | Architecture explorer",
            "architecture page title is incorrect",
        )
        require(
            architecture["pathname"] == f"{base_path}architecture.html",
            "architecture page did not retain the exact project base path",
        )
        require(
            architecture["tabCount"] == 3,
            "architecture scenario set is incomplete",
        )
        require(
            architecture["heading"]
            == "A bounded request becomes a recorded stage decision",
            "initial architecture scenario did not render",
        )
        require(
            architecture["step"] == "Receive command",
            "initial architecture step did not render",
        )
        require(
            architecture["currentImageComplete"],
            "current architecture PNG did not load",
        )
        require(
            architecture["awsImageComplete"],
            "AWS reference architecture PNG did not load",
        )
        require(
            architecture["rootRelativeCount"] == 0,
            "architecture page contains a root-relative link",
        )
        require(
            len(architecture["downloads"]) == 6,
            "architecture download set is incomplete",
        )
        require(
            all(
                urllib.parse.urlsplit(url).scheme == parsed_base.scheme
                and urllib.parse.urlsplit(url).netloc == parsed_base.netloc
                and urllib.parse.urlsplit(url).path.startswith(base_path)
                for url in architecture["downloads"]
            ),
            "architecture download resolved outside the Pages base",
        )

        browser.click('[data-scenario="governance"]')
        browser.wait_for(
            "document.querySelector('#scenario-title')?.textContent "
            "=== 'Agents prepare work; people retain delivery authority'",
            "the Governance scenario",
        )
        require(
            browser.evaluate(
                "document.querySelector('[data-scenario=\"governance\"]')"
                "?.getAttribute('aria-selected')"
            )
            == "true",
            "Governance scenario did not expose selected state",
        )
        first_step = browser.evaluate(
            "document.querySelector('#step-title')?.textContent"
        )
        browser.click("#next-step")
        browser.wait_for(
            "document.querySelector('#step-title')?.textContent "
            f"!== {json.dumps(first_step)}",
            "the architecture Next interaction",
        )
        require(
            browser.evaluate(
                "document.querySelector('#step-title')?.textContent"
            )
            == "Register evidence",
            "Next did not advance the Governance flow",
        )
        if screenshot_directory is not None:
            browser.capture_screenshot(
                screenshot_directory / "architecture-desktop.png"
            )
        assert_mobile_layout(browser, "architecture page")
        if screenshot_directory is not None:
            browser.capture_screenshot(
                screenshot_directory / "architecture-mobile.png"
            )
        browser.clear_mobile_viewport()
        browser.settle()

        external_requests = []
        api_requests = []
        for url in browser.request_urls:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme in {"about", "blob", "data"}:
                continue
            if parsed.scheme not in {"http", "https"}:
                external_requests.append(url)
                continue
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin != allowed_origin or not parsed.path.startswith(base_path):
                external_requests.append(url)
            relative_path = (
                parsed.path[len(base_path) :]
                if parsed.path.startswith(base_path)
                else parsed.path.lstrip("/")
            )
            if relative_path == "api" or relative_path.startswith("api/"):
                api_requests.append(url)
        failed_responses = [
            response
            for response in browser.responses
            if float(response["status"]) >= 400
        ]
        require(
            not external_requests,
            f"page attempted prohibited network requests: {external_requests}",
        )
        require(
            not api_requests,
            f"public site requested API routes: {api_requests}",
        )
        require(
            not browser.websockets,
            f"page opened WebSocket connections: {browser.websockets}",
        )
        require(
            not failed_responses,
            f"browser received failed responses: {failed_responses}",
        )
        require(
            not browser.loading_failures,
            f"browser loading failures: {browser.loading_failures}",
        )
        require(
            not browser.browser_exceptions,
            f"browser exceptions: {browser.browser_exceptions}",
        )
        require(
            not browser.console_errors,
            f"browser console errors: {browser.console_errors}",
        )

    return {
        "ok": True,
        "base_url": base_url,
        "asset_count": len(EXPECTED_ASSETS),
        "pages": ["index.html", "architecture.html"],
        "interaction_count": 2,
        "mobile_width": 390,
        "external_request_count": 0,
        "api_request_count": 0,
        "websocket_count": 0,
        "browser_exception_count": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=DEFAULT_SITE_ROOT,
        help="Local static-site directory to serve.",
    )
    parser.add_argument(
        "--base-path",
        default=DEFAULT_BASE_PATH,
        help="Local project base path, including leading and trailing slash.",
    )
    parser.add_argument(
        "--base-url",
        help="Verify an already-published site instead of starting a local server.",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        help="Optional directory for transient browser screenshots.",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    screenshot_directory = None
    if args.screenshot_dir is not None:
        screenshot_directory = args.screenshot_dir.resolve()
        screenshot_directory.mkdir(parents=True, exist_ok=True)

    try:
        if args.base_url:
            result = verify_browser(args.base_url, screenshot_directory)
        else:
            require(
                args.base_path.startswith("/") and args.base_path.endswith("/"),
                "base path must start and end with '/'",
            )
            site_root = args.site_root.resolve()
            require(
                (site_root / "index.html").is_file(),
                f"site root has no index.html: {site_root}",
            )
            with local_site(site_root, args.base_path) as (base_url, requests):
                result = verify_browser(base_url, screenshot_directory)
                failed = [
                    request
                    for request in requests
                    if int(request["status"]) >= 400
                ]
                require(
                    not failed,
                    f"local static server returned failed responses: {failed}",
                )
                result["local_request_count"] = len(requests)
        if screenshot_directory is not None:
            result["screenshot_directory"] = str(screenshot_directory)
    except (
        BrowserCheckError,
        json.JSONDecodeError,
        OSError,
        UnicodeError,
        urllib.error.URLError,
        websocket.WebSocketException,
    ) as error:
        result = {"ok": False, "error": str(error)}

    json.dump(
        result,
        sys.stdout,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    )
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
