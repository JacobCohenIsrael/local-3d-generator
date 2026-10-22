"""Print a local MCP config block; never edit agent configuration automatically."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--format', choices=('claude', 'codex'), required=True)
parser.add_argument('--port', type=int, default=8765)
args = parser.parse_args()
if not 1024 <= args.port <= 65535:
    parser.error('Port must be between 1024 and 65535')
script = (Path(__file__).resolve().parent / 'mcp_server.py').as_posix()
command_args = ['run', '--script', script, '--port', str(args.port)]
if args.format == 'claude':
    print(json.dumps({'mcpServers': {'local3d': {'command': 'uv', 'args': command_args}}}, indent=2))
else:
    print('[mcp_servers.local3d]')
    print('command = "uv"')
    print('args = ' + json.dumps(command_args))
