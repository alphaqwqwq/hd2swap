"""One-command build pipeline for the HD2Swap addon.

Runs every gate in order and STOPS on the first failure, so a bad build can
never reach the game:

    1. Lua syntax parse
    2. offline smoke test   (real LuaJIT + fake game, pure-logic errors)
    3. end-to-end test       (identify -> draw -> click -> swap -> verify)
    4. package the mod ZIP
    5. verify the built archive (hash + size fields round-trip)

Usage:
    & "D:\\py\\python.exe" D:\\SteamLibrary\\steamai\\HD2Swap\\build.py
    ... build.py --name mods/x/y --src src/x.lua --skip-e2e
"""

import argparse
import os
import subprocess
import sys

# The Windows console defaults to GBK here; force UTF-8 so Chinese log lines
# from the tests don't blow up mid-print.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

PY = r'D:\py\python.exe'
ROOT = r'D:\SteamLibrary\steamai\HD2Swap'
DEFAULT_SRC = os.path.join(ROOT, 'src', 'head_swap.lua')
DEFAULT_NAME = 'mods/hd2swap/head_swap'
DEFAULT_GUID = '7c3f1a52-9e04-4b77-8d21-5a6e0c9b4f13'
DEFAULT_DISPLAY = 'HD2Swap - Head Swap - v2'
ARCHIVE_TOOL = r'D:\SteamLibrary\steamai\HD2ArchiveTool\make_mod.py'


def banner(step, text):
    print()
    print('=' * 72)
    print('  [%s] %s' % (step, text))
    print('=' * 72)


def run(args, label, allow_fail=False):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    print('  $ ' + ' '.join(args[1:]))
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env=env)
    out = (p.stdout or '') + (p.stderr or '')
    for line in out.splitlines()[:80]:
        print('    ' + line)
    if len(out.splitlines()) > 80:
        print('    ... (%d more lines)' % (len(out.splitlines()) - 80))
    if p.returncode != 0 and not allow_fail:
        print()
        print('  !! %s FAILED (exit %d)' % (label, p.returncode))
        sys.exit(1)
    return p.returncode


def step_syntax(src):
    banner('1/5', 'Lua syntax check')
    code = (
        "from luaparser import ast\n"
        "src = open(r'%s', encoding='utf-8').read()\n"
        "ast.parse(src)\n"
        "print('OK  %%d lines, %%d bytes' %% (src.count(chr(10)) + 1, len(src.encode())))\n"
    ) % src
    run([PY, '-c', code], 'syntax')


def step_smoke(src, frames):
    banner('2/5', 'offline smoke test (fake game)')
    run([PY, os.path.join(ROOT, 'test', 'smoke_test.py'), src,
         '--frames', str(frames), '--verbose'], 'smoke')


def step_e2e(src):
    banner('3/5', 'end-to-end test (click -> swap)')
    run([PY, os.path.join(ROOT, 'test', 'e2e_test.py')], 'e2e')


def step_package(src, name, guid, display, out):
    banner('4/5', 'package mod ZIP')
    if os.path.exists(out):
        os.remove(out)
    run([PY, ARCHIVE_TOOL, '--name', name, '--guid', guid,
         '--entry', src, '--output', out, '--display', display], 'package')
    return out


def step_verify(zip_path, name):
    banner('5/5', 'verify built archive')
    code = (
        "import sys, zipfile, struct\n"
        "sys.path.insert(0, r'D:\\SteamLibrary\\steamai\\HD2ArchiveTool')\n"
        "from bingus_build import resource_hash\n"
        "z = zipfile.ZipFile(r'%s')\n"
        "a = z.read('Addon/9ba626afa44a3aa3.patch_0')\n"
        "total = struct.unpack_from('<Q', a, 0x20)[0]\n"
        "stamp = struct.unpack_from('<Q', a, 0x68)[0]\n"
        "a0 = struct.unpack_from('<Q', a, 0xA0)[0]\n"
        "c0 = struct.unpack_from('<I', a, 0xC0)[0]\n"
        "want = resource_hash(%r)\n"
        "ok = (total == len(a)) and (stamp == want) and (a0 == c0 + 8)\n"
        "print('archive size   : %%d (field %%d) %%s' %% (len(a), total, 'MATCH' if total == len(a) else 'MISMATCH'))\n"
        "print('resource hash  : 0x%%016X (want 0x%%016X) %%s' %% (stamp, want, 'MATCH' if stamp == want else 'MISMATCH'))\n"
        "print('0xA0 == 0xC0+8 : %%s (0x%%X vs 0x%%X)' %% ('MATCH' if a0 == c0 + 8 else 'MISMATCH', a0, c0))\n"
        "print('files          : ' + ', '.join(i.filename for i in z.infolist()))\n"
        "sys.exit(0 if ok else 1)\n"
    ) % (zip_path, name)
    run([PY, '-c', code], 'verify')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=DEFAULT_SRC)
    ap.add_argument('--name', default=DEFAULT_NAME)
    ap.add_argument('--guid', default=DEFAULT_GUID)
    ap.add_argument('--display', default=DEFAULT_DISPLAY)
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist', 'HD2Swap-HeadSwap-v2.zip'))
    ap.add_argument('--frames', type=int, default=120)
    ap.add_argument('--skip-syntax', action='store_true')
    ap.add_argument('--skip-smoke', action='store_true')
    ap.add_argument('--skip-e2e', action='store_true')
    a = ap.parse_args()

    print('HD2Swap build pipeline')
    print('  source : %s' % a.src)
    print('  module : %s' % a.name)
    print('  output : %s' % a.out)
    if not os.path.exists(a.src):
        print('ERROR: source not found')
        return 1

    if not a.skip_syntax:
        step_syntax(a.src)
    if not a.skip_smoke:
        step_smoke(a.src, a.frames)
    if not a.skip_e2e:
        step_e2e(a.src)
    step_package(a.src, a.name, a.guid, a.display, a.out)
    step_verify(a.out, a.name)

    print()
    print('=' * 72)
    print('  BUILD OK')
    print('=' * 72)
    print('  %s' % a.out)
    print('  import this ZIP in HD2 Arsenal, enable it with Bingus Shared Loader,')
    print('  then Deploy.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
