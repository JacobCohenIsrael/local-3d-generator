"""Actual HTTP bridge and stdio MCP checks; no worker or GPU inference."""
import asyncio
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest

from PIL import Image
from mcp_server import AppBridge
from web_app import Workshop, handler


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = Workshop(self.root)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        self.port = self.server.server_address[1]
        self.server.RequestHandlerClass = handler(self.app, self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.bridge = AppBridge(self.port)
        self.image = self.root / 'front.png'
        Image.new('RGB', (64, 64), 'red').save(self.image)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)
        self.temp.cleanup()

    def test_live_app_queue_status_cancel_and_download(self):
        status = self.bridge.status()
        self.assertTrue(status['mcp_ready'])
        self.assertTrue(status['app_ready'])
        job_id = self.bridge.generate('Test mesh', {'front': str(self.image)},
                                      {'texture': 'photo_basecolor'})['id']
        self.assertEqual(self.bridge.get_job(job_id)['state'], 'queued')
        self.assertEqual(len(self.bridge.list_jobs()), 1)
        folder = self.app.jobs / job_id / 'asset'
        folder.mkdir()
        (folder / 'unity-package.zip').write_bytes(b'test-export')
        target = self.root / 'download.zip'
        result = self.bridge.download(job_id, 'package', str(target))
        self.assertEqual(result['bytes'], 11)
        self.assertEqual(target.read_bytes(), b'test-export')
        with self.assertRaises(FileExistsError):
            self.bridge.download(job_id, 'package', str(target))
        self.assertEqual(target.read_bytes(), b'test-export')
        self.bridge.cancel(job_id)
        self.assertEqual(self.bridge.get_job(job_id)['state'], 'cancelled')

    def test_incomplete_download_removes_only_its_partial_file(self):
        import io
        from unittest.mock import patch
        job_id = 'a' * 32
        target = self.root / 'partial.zip'
        response = io.BytesIO(b'short')
        response.headers = {'Content-Length': '100'}
        with patch.object(self.bridge, 'get_job', return_value={'downloads': ['package']}):
            with patch.object(self.bridge.opener, 'open', return_value=response):
                with self.assertRaisesRegex(ValueError, 'Incomplete'):
                    self.bridge.download(job_id, 'package', str(target))
        self.assertFalse(target.exists())

    def test_validation_and_missing_export(self):
        for views in ({'left': str(self.image)}, {'front': 'relative.png'},
                      {'front': str(self.root / 'missing.png')}):
            with self.assertRaises(ValueError):
                self.bridge.generate('Bad', views)
        with self.assertRaisesRegex(ValueError, 'Invalid triangles'):
            self.bridge.generate('Bad', {'front': str(self.image)}, {'triangles': 2})
        with self.assertRaisesRegex(ValueError, 'Strata vision'):
            # Keep this independent of a developer's local vision config.
            from unittest.mock import patch
            with patch.object(self.bridge, 'status', return_value={'health': {'vision_configured': False}}):
                self.bridge.generate('Bad', {'front': str(self.image)}, extra_photos=[str(self.image)])
        with self.assertRaises(ValueError):
            self.bridge.get_job('../jobs')
        with self.assertRaisesRegex(ValueError, '404'):
            self.bridge.get_job('0' * 32)
        job_id = self.bridge.generate('Test', {'front': str(self.image)})['id']
        with self.assertRaisesRegex(ValueError, 'not available'):
            self.bridge.download(job_id, 'package', str(self.root / 'missing.zip'))
        self.assertFalse((self.root / 'missing.zip').exists())

    def test_single_job_lookup_beyond_history_window(self):
        first = self.bridge.generate('Old', {'front': str(self.image)})['id']
        with self.app.db() as db:
            # No file creation or inference is needed to test the query boundary.
            db.executemany('INSERT INTO jobs VALUES (?,?,?,?,NULL)',
                           [(f'{i:032x}', 'Newer', 'completed', 9999999999 + i) for i in range(101)])
        self.assertEqual(len(self.bridge.list_jobs()), 100)
        self.assertEqual(self.bridge.get_job(first)['name'], 'Old')

    def test_offline_status_is_actionable(self):
        self.server.shutdown()
        self.server.server_close()
        status = self.bridge.status()
        self.assertTrue(status['mcp_ready'])
        self.assertFalse(status['app_reachable'])
        self.assertIn('Start Local 3D.cmd', status['message'])

    def test_no_proxy_redirects_or_remote_host_option(self):
        with self.assertRaises(ValueError):
            AppBridge(80)
        with self.assertRaises(ValueError):
            AppBridge('https://example.com')
        from mcp_server import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com'))

    @unittest.skipUnless(importlib.util.find_spec('mcp'), 'Run in the isolated MCP test environment for protocol checks')
    def test_real_stdio_initialize_ping_tools_and_offline_recovery(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        async def check():
            params = StdioServerParameters(command=sys.executable, args=[
                '-B', str(Path(__file__).with_name('mcp_server.py')), '--port', str(self.port)],
                cwd=str(self.root))
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    await session.send_ping()
                    tools = await session.list_tools()
                    self.assertEqual({t.name for t in tools.tools}, {
                        'local3d_status', 'list_jobs', 'get_job', 'generate_asset',
                        'cancel_job', 'download_asset'})
                    status = await session.call_tool('local3d_status', {})
                    self.assertFalse(status.isError)
                    self.assertTrue(json.loads(status.content[0].text)['app_ready'])
                    generated = await session.call_tool('generate_asset', {
                        'name': 'Protocol test', 'views': {'front': str(self.image)}})
                    self.assertFalse(generated.isError)
                    job_id = json.loads(generated.content[0].text)['id']
                    job = await session.call_tool('get_job', {'job_id': job_id})
                    self.assertEqual(json.loads(job.content[0].text)['state'], 'queued')
                    cancelled = await session.call_tool('cancel_job', {'job_id': job_id})
                    self.assertFalse(cancelled.isError)
                    invalid = await session.call_tool('get_job', {'job_id': '../escape'})
                    self.assertTrue(invalid.isError)
                    self.server.shutdown()
                    self.server.server_close()
                    offline = await session.call_tool('local3d_status', {})
                    self.assertFalse(json.loads(offline.content[0].text)['app_ready'])
                    await session.send_ping()
                    # The same MCP connection recovers when the app returns.
                    self.server = ThreadingHTTPServer(('127.0.0.1', self.port), handler(self.app, self.port))
                    self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
                    self.thread.start()
                    recovered = await session.call_tool('local3d_status', {})
                    self.assertTrue(json.loads(recovered.content[0].text)['app_ready'])

        asyncio.run(asyncio.wait_for(check(), timeout=30))


if __name__ == '__main__':
    unittest.main()
