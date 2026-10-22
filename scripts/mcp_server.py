# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp==1.26.0"]
# ///
"""Local stdio MCP bridge; no GPU imports or independent generation worker."""
import argparse
import base64
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

MAX_IMAGE = 12 * 1024 * 1024
MAX_TOTAL = 48 * 1024 * 1024
DOWNLOADS = {'fbx', 'glb', 'blend', 'preview', 'package', 'report', 'color',
             'coverage', 'inferred', 'material', 'selection'}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TokenParser(HTMLParser):
    token = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'local3d-token':
            self.token = attrs.get('content')


class AppBridge:
    def __init__(self, port=8765):
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('Port must be between 1024 and 65535')
        self.url = f'http://127.0.0.1:{port}'
        # Local calls must not go through a configured proxy or follow redirects.
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path, data=None, *, limit=32 * 1024 * 1024):
        headers = {}
        if data is not None:
            parser = TokenParser()
            parser.feed(self.request('/').decode('utf-8'))
            if not parser.token or parser.token == '__APP_TOKEN__':
                raise ValueError('Local app token unavailable; restart the updated app')
            headers = {'X-Local3D-Token': parser.token, 'Content-Type': 'application/json'}
            data = json.dumps(data).encode('utf-8')
        request = Request(self.url + path, data=data, headers=headers)
        try:
            with self.opener.open(request, timeout=10) as response:
                content = response.read(limit + 1)
                if len(content) > limit:
                    raise ValueError('Local app response exceeds the size limit')
                return content
        except HTTPError as error:
            # Return the app's validation message without leaking HTML/token content.
            try:
                message = json.loads(error.read(4096)).get('error', 'Request failed')
            except (ValueError, AttributeError):
                message = 'Request failed'
            raise ValueError(f'Local app HTTP {error.code}: {message}') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('Local app unavailable. Start Local 3D.cmd, then retry the status check.') from None

    def json(self, path, data=None):
        return json.loads(self.request(path, data))

    def status(self):
        """MCP is alive if this returns; app readiness is a separate check."""
        try:
            health = self.json('/api/health')
            if not isinstance(health, dict) or health.get('service') != 'local-3d-generator':
                raise ValueError('Unexpected service or older app. Restart the updated Local 3D app.')
            return {'mcp_ready': True, 'app_reachable': True,
                    'app_ready': health.get('ready') is True, 'url': self.url,
                    'health': health,
                    'note': 'Model presence is not a RAM/VRAM check or a successful generation.'}
        except (ValueError, TypeError) as error:
            return {'mcp_ready': True, 'app_reachable': False, 'app_ready': False,
                    'url': self.url, 'message': str(error)}

    @staticmethod
    def job_id(value):
        if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
            raise ValueError('Expected a 32-character job ID returned by generate_asset/list_jobs')
        return value

    def list_jobs(self):
        return self.json('/api/jobs')

    def get_job(self, job_id):
        result = self.json(f'/api/jobs/{self.job_id(job_id)}')
        result['download_urls'] = {
            key: f'{self.url}/api/jobs/{job_id}/files/{key}' for key in result['downloads']}
        return result

    def generate(self, name, views, settings=None, extra_photos=None):
        if not isinstance(views, dict) or 'front' not in views or set(views) - {'front', 'left', 'back', 'right'}:
            raise ValueError('Provide a front image path and optional left/back/right paths')
        if extra_photos is None:
            extra_photos = []
        if not isinstance(extra_photos, list) or len(views) + len(extra_photos) > 16:
            raise ValueError('Use at most 16 total images')
        total = 0

        def encode(filename):
            nonlocal total
            path = Path(filename).expanduser()
            if not path.is_absolute() or not path.is_file():
                raise ValueError('Images must be existing absolute local file paths')
            with path.open('rb') as stream:
                content = stream.read(MAX_IMAGE + 1)
            if not content or len(content) > MAX_IMAGE:
                raise ValueError('Each image must be nonempty and at most 12 MiB')
            total += len(content)
            if total > MAX_TOTAL:
                raise ValueError('Combined images must be at most 48 MiB')
            return base64.b64encode(content).decode('ascii')

        if extra_photos and not self.status().get('health', {}).get('vision_configured'):
            raise ValueError('Extra photos require Strata vision. Use labelled views or follow MORE_ANGLES.md.')
        # The HTTP boundary validates image format, dimensions and all settings.
        payload = {'name': name, 'views': {key: encode(path) for key, path in views.items()},
                   'settings': settings if settings is not None else {},
                   'extra_views': [{'name': Path(path).name[:80], 'image': encode(path)} for path in extra_photos]}
        result = self.json('/api/jobs', payload)
        return {'id': result['id'], 'state': 'queued',
                'next': 'Use get_job to poll. Submitting again creates another job; do not retry blindly.'}

    def cancel(self, job_id):
        return self.json(f'/api/jobs/{self.job_id(job_id)}/cancel', {})

    def download(self, job_id, kind, destination):
        job_id = self.job_id(job_id)
        if kind not in DOWNLOADS:
            raise ValueError('Unknown download type')
        target = Path(destination).expanduser()
        if not target.is_absolute() or not target.parent.is_dir():
            raise ValueError('Use an absolute destination with an existing parent directory')
        job = self.get_job(job_id)
        if kind not in job['downloads']:
            raise ValueError('This download is not available yet; check get_job')
        # An exclusive create never overwrites user data. Remove only our partial file.
        created = False
        try:
            with self.opener.open(f'{self.url}/api/jobs/{job_id}/files/{kind}', timeout=30) as response:
                expected = response.headers.get('Content-Length')
                with target.open('xb') as output:
                    created = True
                    total = 0
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > 1024 * 1024 * 1024:
                            raise ValueError('Download exceeds 1 GiB limit')
                        output.write(chunk)
                    if expected is not None and total != int(expected):
                        raise ValueError('Incomplete download; partial file removed')
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise
        return {'destination': str(target), 'bytes': total, 'kind': kind}


def build_server(bridge):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations

    server = FastMCP('Local 3D Generator', instructions=(
        'Check local3d_status before using the local app. A connected MCP bridge does not mean '
        'the app or models are ready. Generate only when asked; GPU jobs can take minutes. '
        'Poll get_job rather than resubmitting. Never retry a crashed/OOM job automatically. '
        'Use download_asset for an explicitly requested destination; inspect quality before Unity use.'))
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                            idempotentHint=False, openWorldHint=False)

    @server.tool(annotations=read)
    def local3d_status() -> dict:
        """Check MCP liveness, running app availability and installed model flags; no inference."""
        return bridge.status()

    @server.tool(annotations=read)
    def list_jobs() -> list[dict]:
        """List the latest 100 jobs, including IDs, states, progress and available downloads."""
        return bridge.list_jobs()

    @server.tool(annotations=read)
    def get_job(job_id: str) -> dict:
        """Read a job's progress, reports and export URLs. Poll this instead of resubmitting."""
        return bridge.get_job(job_id)

    @server.tool(annotations=write)
    def generate_asset(name: str, views: dict[str, str], settings: dict | None = None,
                       extra_photos: list[str] | None = None) -> dict:
        """Queue generation from absolute local image paths. views needs front; optional left/back/right.

        Runs GPU inference asynchronously. Only submit when the user requests generation.
        settings: quality balanced/detailed; background object/person/keep; triangles 500..200000;
        height 0.1..20 meters; texture none/photo_basecolor; texture_size 512/1024;
        texture_fill neutral/nearest_surface (estimated); planner preset/strata;
        max_attempts 1/2 (only geometric rejection); allow_flat boolean.
        Defaults match the HTTP API (texture none). Extra photos require configured Strata vision.
        Images: JPEG/PNG/WebP, at least 64 pixels per side, at most 20 megapixels,
        12 MiB each, 16 photos and 48 MiB total. Returns a job ID immediately.
        """
        return bridge.generate(name, views, settings, extra_photos)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True,
                                           idempotentHint=True, openWorldHint=False))
    def cancel_job(job_id: str) -> dict:
        """Cancel a queued/running job and its owned work. Originals/history remain saved."""
        return bridge.cancel(job_id)

    @server.tool(annotations=write)
    def download_asset(job_id: str, kind: str, destination: str) -> dict:
        """Save an available export to an absolute local destination; never overwrite a file.

        kind: package (FBX + colors Unity ZIP), fbx, glb, blend, preview, report,
        color, coverage, inferred, material or selection. Parent directory must exist.
        Use package for Unity with photo colors; FBX alone lacks external PNGs.
        """
        return bridge.download(job_id, kind, destination)

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765, help='Existing app loopback port')
    args = parser.parse_args()
    build_server(AppBridge(args.port)).run(transport='stdio')


if __name__ == '__main__':
    main()
