import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--repo', type=Path, required=True)
p.add_argument('--private', type=Path, required=True)
p.add_argument('--ref', required=True, help='Published Git tag or immutable candidate commit')
p.add_argument('--version', required=True, help='Expected installed plugin version')
p.add_argument('--output', type=Path, required=True)
args = p.parse_args()
repo, private = args.repo.resolve(), args.private.resolve()
if private.is_relative_to(repo) or args.output.exists():
    raise ValueError('private directory must be outside repository and output must be new')
private.mkdir(parents=True, exist_ok=False)
home = private / 'codex-home'
home.mkdir()
auth = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'auth.json'
shutil.copyfile(auth, home / 'auth.json')
if os.name != 'nt':
    (home / 'auth.json').chmod(0o600)
env = {**os.environ, 'CODEX_HOME': str(home), 'UV_CACHE_DIR': str(private / 'uv-cache'),
       'RATCHET_CONFIG': str(private / 'settings.json')}
env.pop('UV_OFFLINE', None)
codex = shutil.which('codex')
def run(command, label, environment=None, timeout=300):
    result = subprocess.run(command, env=environment or env, cwd=repo, text=True, encoding='utf-8',
                            capture_output=True, timeout=timeout)
    (private / (label + '.stdout')).write_text(result.stdout, encoding='utf-8')
    (private / (label + '.stderr')).write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError(label + ' failed; inspect private log')
    return result.stdout
run([codex, 'plugin', 'marketplace', 'add', 'anthony-maio/codex-decision-layer', '--ref', args.ref, '--json'], 'marketplace')
run([codex, 'plugin', 'add', 'ratchet@codex-decision-layer', '--json'], 'install')
installed = []
for path in (home / 'plugins/cache').rglob('plugin.json'):
    value = json.loads(path.read_text())
    if value.get('name') == 'ratchet' and value.get('version') == args.version:
        installed.append(path.parent.parent)
if len(installed) != 1:
    raise ValueError('expected exactly one installed tagged plugin')
manifest = installed[0] / '.mcp.json'
if manifest.read_bytes() != (repo / 'plugins/ratchet/.mcp.json').read_bytes():
    raise ValueError('installed manifest differs from candidate')
server = json.loads(manifest.read_bytes())['mcpServers']['ratchet']
launcher = [server['command'], *server['args']]
prefix = 'codex-evidence-selector[mcp] @ git+https://github.com/anthony-maio/codex-decision-layer.git@'
package_commit = launcher[2].removeprefix(prefix)
if (len(package_commit) != 40 or any(c not in '0123456789abcdef' for c in package_commit)
        or launcher != ['uvx', '--from', prefix + package_commit, 'ratchet', 'mcp']):
    raise ValueError('unexpected tag launcher')
online = json.loads(run([sys.executable, 'tests/smoke_ratchet_mcp.py', '--manifest', str(manifest)], 'online'))
offline = json.loads(run([sys.executable, 'tests/smoke_ratchet_mcp.py', '--manifest', str(manifest)], 'offline', {**env, 'UV_OFFLINE': '1'}))
identity_code = '''import importlib.metadata as m, pathlib, hashlib, json, evidence_selector.ratchet
d=m.distribution('codex-evidence-selector')
root=pathlib.Path(evidence_selector.ratchet.__file__).parent
print(json.dumps({'version':d.version,'source':json.loads(d.read_text('direct_url.json')),'python':__import__('platform').python_version(),'dependencies':dict(sorted((x.metadata['Name'],x.version) for x in m.distributions())),'implementation_sha256':{str(p.relative_to(root)).replace('\\\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))}}))'''
identity = json.loads(run(launcher[:-2] + ['python', '-c', identity_code], 'identity', {**env, 'UV_OFFLINE': '1'}))
marketplace_commit = subprocess.check_output(['git', 'rev-parse', args.ref + '^{commit}'], cwd=repo, text=True).strip()
if identity['source']['vcs_info']['commit_id'] != package_commit or identity['version'] != args.version:
    raise ValueError('loaded package identity differs from installed manifest')
for name, digest in identity['implementation_sha256'].items():
    if hashlib.sha256((repo / 'evidence_selector/ratchet' / name).read_bytes()).hexdigest() != digest:
        raise ValueError('loaded implementation differs from candidate')
records = private / 'records'
records.mkdir()
replay = json.loads((repo / 'evidence_selector/ratchet/data/replay.json').read_text())
for index, events in enumerate(replay['examples'][0]['records']):
    (records / f'attempt-{index}.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n', encoding='utf-8', newline='\n')
run(launcher[:-1] + ['configure', '--root', str(records)], 'configure')
run([sys.executable, 'scripts/probe_ratchet_plugin.py', '--private-dir', str(private / 'probe')], 'probe', timeout=240)
sys.path.insert(0, str(repo / 'scripts'))
from verify_ratchet_probe import verify
result = verify(private / 'probe')
events = [json.loads(line) for line in (private / 'probe/worker.jsonl').read_text().splitlines()]
if any(e.get('item', {}).get('type') == 'command_execution' for e in events):
    raise ValueError('read-only probe executed a shell command')
result.update(scope='Plugin installed from the specified marketplace revision in a fresh isolated Codex home',
              launch='Unmodified installed uvx manifest using saved record root and immutable package commit',
              marketplace_ref=args.ref, marketplace_commit=marketplace_commit, platform=platform.system(),
              package_identity=identity, online_launcher=online, offline_launcher=offline,
              first_install_cache='fresh dedicated uv cache', global_codex_configuration_modified=False,
              private_credentials_and_sessions_published=False)
args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'status':result['integration_status'],'platform':platform.system(),'ref':args.ref,'commit':marketplace_commit}))
