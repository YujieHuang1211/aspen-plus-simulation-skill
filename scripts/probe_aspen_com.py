"""Probe whether Aspen Plus can be driven through COM on this machine.

Usage:
    PYTHONIOENCODING=utf-8 python probe_aspen_com.py [--timeout 90] [--progid Apwn.Document.37.0]

What it does, in order:
 1. lists Apwn.Document.* ProgIDs registered in HKCR (V11 = 37.0, V12 = 38.0 ...),
    including the in-process variants Apwn.Document.IP*, which are tried first;
 2. lists running AspenPlus.exe / apmain.exe processes (a GUI session may hold
    the only license seat);
 3. for each candidate ProgID, in a child process with a timeout:
    Dispatch -> InitNew2 -> read Engine version -> Close.
    The child is killed on timeout, so a hung COM server cannot hang the probe.

Exit code 0 means one ProgID worked end to end; the script prints which one
and the next step.  Otherwise it prints a diagnosis per ProgID.
Needs pywin32 (pip install pywin32).  Read-only: it never opens a user model.
"""
import argparse
import subprocess
import sys

CHILD = r'''
import sys, time, pythoncom, win32com.client as w
pythoncom.CoInitialize()
t = time.time()
a = w.Dispatch(sys.argv[1])
print('STEP dispatch %.1fs' % (time.time() - t), flush=True)
a.InitNew2()
print('STEP initnew %.1fs' % (time.time() - t), flush=True)
print('STEP unit sets', [e.Name for e in a.Tree.FindNode(r"\Data\Setup\Units-Sets").Elements], flush=True)
a.Close()
print('OK %.1fs' % (time.time() - t), flush=True)
'''

# HRESULTs seen in practice and what they mean for the next step
KNOWN = [
    (('0x800401f3', '-2147221005', 'invalid class string'),
     'Invalid class string: this ProgID is not registered. Wrong version number, '
     'or the Aspen Plus COM server was never registered (repair install as admin).'),
    (('0x80080005', '-2146959355', 'server execution failed'),
     'Server execution failed: the class is registered but the COM server did not start '
                   'within the DCOM timeout (Event Log: DCOM 10010). Seen on this kind of machine when the '
                   'license only allows the interactive GUI, when the caller runs in a sandbox / different '
                   'session or elevation level, or when another instance holds the single seat. '
     'Try once from a normal (non-sandboxed) shell with the GUI closed; if it still fails, '
     'fall back to GUI + computer use.'),
    (('license',),
     'License error from the engine: check the SLM/Sentinel license server, and whether a GUI '
     'session already holds the only seat (close it, or drive that GUI instead).'),
    (('no module named',),
     'pywin32 missing in this Python: pip install pywin32.'),
]


def registered_progids():
    try:
        import winreg
    except ImportError:
        return []
    out = []
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, '') as root:
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            if name.lower().startswith('apwn.document'):
                out.append(name)
            i += 1
    return sorted(out)


def running_aspen():
    try:
        txt = subprocess.run(['tasklist', '/fo', 'csv', '/nh'], capture_output=True, text=True,
                             errors='replace').stdout
    except OSError:
        return []
    names = ('aspenplus.exe', 'apmain.exe', 'apwn.exe', 'aspenplusgui.exe')
    return [ln.split(',')[0].strip('"') + ' pid ' + ln.split(',')[1].strip('"')
            for ln in txt.splitlines() if ln.split(',')[0].strip('"').lower() in names]


def diagnose(text):
    low = text.lower()
    for keys, msg in KNOWN:
        if any(k in low for k in keys):
            return msg
    return None


def probe(progid, timeout):
    try:
        p = subprocess.run([sys.executable, '-c', CHILD, progid], capture_output=True, text=True,
                           timeout=timeout, errors='replace')
        out = (p.stdout + p.stderr).strip()
        return ('ok' if 'OK ' in p.stdout else 'error'), out
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b'').decode(errors='replace') if isinstance(e.stdout, bytes) else (e.stdout or ''))
        return 'timeout', out.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=90)
    ap.add_argument('--progid', action='append')
    args = ap.parse_args()

    regs = registered_progids()
    print('Registered ProgIDs:', ', '.join(regs) or 'none found')
    procs = running_aspen()
    print('Running Aspen processes:', ', '.join(procs) or 'none')
    # In-process ('.IP') first: on V11 the out-of-process server hung in Dispatch
    # while Apwn.Document.IP worked.  A hang costs the full timeout, so try the
    # likely winner first and stop at the first success.
    cands = args.progid or sorted(regs, key=lambda r: ('.IP' not in r, r)) or ['Apwn.Document']

    for pid in cands:
        print(f'\n== {pid}')
        status, out = probe(pid, args.timeout)
        print(out[-1500:] if out else '(no output)')
        if status == 'ok':
            print(f'\nRESULT: COM works with {pid}. Use aspen_com.py: Aspen(bkp, progid={pid!r}). '
                  f'InitFromArchive2 takes .bkp only; a hand-written .inp needs one GUI open '
                  f'(or build the model through COM).')
            return 0
        if status == 'timeout':
            step = 'after Dispatch' if 'STEP dispatch' in out else 'inside Dispatch'
            print(f'DIAGNOSIS: hung {step} for >{args.timeout:.0f}s. The COM object '
                  f'{"exists but the engine/license call blocks" if "STEP dispatch" in out else "server never answered"}; '
                  f'a modal dialog (license, upgrade prompt) in another session is a common cause. '
                  f'An out-of-process server may start late and linger as AspenPlus.exe; '
                  f'it usually exits by itself.')
        else:
            print('DIAGNOSIS:', diagnose(out) or 'unrecognised error, read the traceback above.')

    print('\nRESULT: COM unavailable. Next: try the command-line engine once '
          '(aspsetup.bat, then "aspen <runid>"), and if that also fails with a license error, '
          'write the .inp and run it in the GUI (by hand or computer use; see codex_brief_template.md).')
    return 1


if __name__ == '__main__':
    sys.exit(main())
