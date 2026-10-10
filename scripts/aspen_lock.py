"""Queue for a single-seat Aspen license shared by parallel agents or scripts.

    python aspen_lock.py acquire <run-id>   # blocks until the seat is free
    python aspen_lock.py release <run-id>

The license is one seat per machine, so every job should use the same lock:
the default .aspen_lock next to this script.  ASPEN_LOCK_DIR overrides it only
for testing the script itself.
A lock older than 30 min is treated as stale and taken over; an agent that
died while holding it can also be released by hand with its run-id.
"""
import os, sys, time
BASE = os.environ.get('ASPEN_LOCK_DIR') or os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, '.aspen_lock')
LOG = os.path.join(BASE, 'aspen_lock.log')
STALE = 30 * 60

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(time.strftime('%H:%M:%S ') + msg + '\n')

cmd, rid = sys.argv[1], sys.argv[2]
if cmd == 'acquire':
    t0 = time.time()
    while True:
        try:
            os.mkdir(D)
            open(os.path.join(D, 'owner'), 'w').write(rid)
            log(f'acquire {rid} after {time.time() - t0:.0f}s')
            print(f'lock acquired by {rid}')
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(D) > STALE:
                    owner = open(os.path.join(D, 'owner')).read()
                    log(f'stale lock of {owner} taken by {rid}')
                    os.remove(os.path.join(D, 'owner')); os.rmdir(D)
                    continue
            except OSError:
                pass
            time.sleep(5)
elif cmd == 'release':
    try:
        owner = open(os.path.join(D, 'owner')).read()
        if owner == rid:
            os.remove(os.path.join(D, 'owner')); os.rmdir(D)
            log(f'release {rid}'); print('released')
        else:
            print(f'lock held by {owner}, not {rid}; nothing released')
    except OSError:
        print('no lock held')
