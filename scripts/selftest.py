"""Regression test of this skill's verified claims against the local Aspen.

    PYTHONIOENCODING=utf-8 python selftest.py            # all cases
    PYTHONIOENCODING=utf-8 python selftest.py smr radfrac

Run it after an Aspen upgrade, on a new machine, or after editing
aspen_com.py.  Each case builds a small model from a blank document through
COM (one subprocess per case, because one document per process), compares the
result with the value recorded in the skill, and prints PASS / FAIL.  It also
checks that the methanation trap still shows up, and that the trusted flag
catches a wrong component name.  Holds the license lock while running.
Reference values: Aspen Plus V11 (37.0), 2026-10-10.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B, S = '\\Data\\Blocks\\', '\\Data\\Streams\\'
K, ATM = 273.15, 1 / 1.01325

# case -> list of (label, extractor expression on result dict, expected, abs tolerance)
EXPECT = {
    'smr':        [('CH4 conversion', 'r["conv"]', 0.763, 0.005)],
    'trap':       [('MeOH with CH4 allowed (trap)', 'r["x"]["MEOH"]', 0.0, 1e-4),
                   ('CH4 with CH4 allowed (trap)', 'r["x"]["CH4"]', 0.463, 0.01)],
    'meoh_requil': [('MeOH mole frac, REquil 250 C 80 bar', 'r["x"]["MEOH"]', 0.269, 0.005)],
    'msr':        [('CO dry %, MSR 250 C 1.5 bar', 'r["dry"]["CO"]', 1.40, 0.05),
                   ('H2 dry %', 'r["dry"]["H2"]', 74.65, 0.1)],
    'wgs':        [('CO dry %, shift 350 C 30 bar', 'r["dry"]["CO"]', 1.45, 0.05)],
    'radfrac':    [('MeOH in distillate', 'r["xD"]', 0.991, 0.002),
                   ('reboiler kW', 'r["QR_kW"]', 13.79, 0.1)],
    'sep':        [('H2 product kmol/h', 'r["h2p"]', 0.6375, 1e-4)],
    'compr':      [('outlet C', 'r["Tout_C"]', 193.8, 0.5), ('WNET unit', 'r["wnet_unit"]', 'kW', None)],
    'badname':    [('trusted is False for CH3OH', 'r["trusted"]', False, None)],
}

CHILD = r'''
import json, sys
sys.path.insert(0, HERE)
from aspen_com import Aspen
case = sys.argv[1]
B, S, K, ATM = '\\Data\\Blocks\\', '\\Data\\Streams\\', 273.15, 1 / 1.01325
def feed(ap, s, T, P, fl):
    ap.set(S + s + '\\Input\\TEMP\\MIXED', T + K); ap.set(S + s + '\\Input\\PRES\\MIXED', P * ATM)
    for c, f in fl.items(): ap.set(S + s + '\\Input\\FLOW\\MIXED\\' + c, f)
def x(ap, s, cs): return {c: ap.get(S + s + '\\Output\\MOLEFRAC\\MIXED\\' + c) or 0.0 for c in cs}
def dry(d):
    d = {k: v for k, v in d.items() if k != 'WATER'}; t = sum(d.values()); return {k: 100 * v / t for k, v in d.items()}
def base(ap, comps, method):
    ap.set_units('MET'); ap.add_components(*comps)
    ap.set('\\Data\\Properties\\Specifications\\Input\\GBASEOPSET', method)
def requil(ap, T, P):
    ap.add_block('Q', 'REQUIL'); ap.connect('Q', 'F(IN)', 'F'); ap.connect('Q', 'V(OUT)', 'V'); ap.connect('Q', 'L(OUT)', 'L')
    ap.set(B + 'Q\\Input\\TEMP', T + K); ap.set(B + 'Q\\Input\\PRES', P * ATM)
r = {}
with Aspen() as ap:
    if case == 'smr':
        base(ap, ['CH4', ('WATER', 'H2O'), 'H2', 'CO', 'CO2'], 'PENG-ROB')
        ap.add_block('G', 'RGIBBS'); ap.connect('G', 'F(IN)', 'F'); ap.connect('G', 'P(OUT)', 'P')
        feed(ap, 'F', 25, 30, {'CH4': 1, 'WATER': 3}); ap.set(B + 'G\\Input\\TEMP', 850 + K); ap.set(B + 'G\\Input\\PRES', 30 * ATM)
        st = ap.run(); X = x(ap, 'P', ['CH4', 'CO', 'CO2']); r['conv'] = 1 - X['CH4'] / sum(X.values())
    elif case == 'trap':
        base(ap, ['H2', 'CO', 'CO2', ('MEOH', 'METHANOL'), ('WATER', 'H2O'), 'CH4'], 'PENG-ROB')
        ap.add_block('G', 'RGIBBS'); ap.connect('G', 'F(IN)', 'F'); ap.connect('G', 'P(OUT)', 'P')
        feed(ap, 'F', 25, 80, {'H2': 70, 'CO': 20, 'CO2': 7, 'CH4': 3}); ap.set(B + 'G\\Input\\TEMP', 250 + K); ap.set(B + 'G\\Input\\PRES', 80 * ATM)
        st = ap.run(); r['x'] = x(ap, 'P', ['MEOH', 'CH4'])
    elif case == 'meoh_requil':
        base(ap, ['H2', 'CO', 'CO2', ('MEOH', 'METHANOL'), ('WATER', 'H2O'), 'CH4'], 'PENG-ROB'); requil(ap, 250, 80)
        feed(ap, 'F', 25, 80, {'H2': 70, 'CO': 20, 'CO2': 7, 'CH4': 3})
        ap.add_reaction('Q', {'CO': 1, 'H2': 2}, {'MEOH': 1}, rxn=1); ap.add_reaction('Q', {'CO2': 1, 'H2': 1}, {'CO': 1, 'WATER': 1}, rxn=2)
        st = ap.run(); r['x'] = x(ap, 'V', ['MEOH'])
    elif case in ('msr', 'wgs'):
        base(ap, [('MEOH', 'METHANOL'), ('WATER', 'H2O'), 'H2', 'CO', 'CO2', 'CH4'], 'PENG-ROB')
        if case == 'msr':
            requil(ap, 250, 1.5); feed(ap, 'F', 25, 1.5, {'MEOH': 1, 'WATER': 1.5})
            ap.add_reaction('Q', {'MEOH': 1, 'WATER': 1}, {'CO2': 1, 'H2': 3}, rxn=1)
            ap.add_reaction('Q', {'CO2': 1, 'H2': 1}, {'CO': 1, 'WATER': 1}, rxn=2)
        else:
            requil(ap, 350, 30); feed(ap, 'F', 350, 30, {'CH4': 0.0647, 'H2': 0.7229, 'CO': 0.1268, 'CO2': 0.0856, 'WATER': 0.6})
            ap.add_reaction('Q', {'CO': 1, 'WATER': 1}, {'CO2': 1, 'H2': 1}, rxn=1)
        st = ap.run(); r['dry'] = dry(x(ap, 'V', ['MEOH', 'WATER', 'H2', 'CO', 'CO2', 'CH4']))
    elif case == 'radfrac':
        base(ap, [('MEOH', 'METHANOL'), ('WATER', 'H2O')], 'NRTL')
        ap.add_block('T', 'RADFRAC'); ap.connect('T', 'F(IN)', 'F'); ap.connect('T', 'LD(OUT)', 'D'); ap.connect('T', 'B(OUT)', 'W')
        feed(ap, 'F', 25, 1.01325, {'MEOH': 0.5, 'WATER': 0.5}); T = B + 'T\\Input\\'
        ap.set(T + 'NSTAGE', 15); ap.set(T + 'CONDENSER', 'TOTAL'); ap.set(T + 'FEED_STAGE\\F', 8)
        ap.set(T + 'PRES1', 1.0); ap.set(T + 'BASIS_RR', 1.5); ap.set(T + 'D:F', 0.5)
        st = ap.run(); r['xD'] = x(ap, 'D', ['MEOH'])['MEOH']
        q = B + 'T\\Output\\REB_DUTY'; r['QR_kW'] = ap.get(q) * (4.184e-3 if 'cal' in ap.unit(q).lower() else 1)
    elif case == 'sep':
        base(ap, ['H2', 'CO', 'CO2', 'CH4'], 'PENG-ROB')
        ap.add_block('PSA', 'SEP'); ap.connect('PSA', 'F(IN)', 'F'); ap.connect('PSA', 'P(OUT)', 'H2P'); ap.connect('PSA', 'P(OUT)', 'TAIL')
        feed(ap, 'F', 40, 20, {'H2': 0.75, 'CO': 0.03, 'CO2': 0.18, 'CH4': 0.04})
        for c, v in {'H2': 0.85, 'CO': 0, 'CO2': 0, 'CH4': 0}.items(): ap.set(B + 'PSA\\Input\\FRACS\\H2P\\MIXED\\' + c, v)
        st = ap.run(); r['h2p'] = ap.get(S + 'H2P\\Output\\MOLEFLMX\\MIXED')
    elif case == 'compr':
        base(ap, ['H2'], 'PENG-ROB')
        ap.add_block('K1', 'COMPR'); ap.connect('K1', 'F(IN)', 'F'); ap.connect('K1', 'P(OUT)', 'P')
        feed(ap, 'F', 40, 1.0, {'H2': 1.0})
        ap.set(B + 'K1\\Input\\TYPE', 'ISENTROPIC'); ap.set(B + 'K1\\Input\\OPT_SPEC', 'PRES')
        ap.set(B + 'K1\\Input\\PRES', 3.0 * ATM); ap.set(B + 'K1\\Input\\SEFF', 0.75)
        st = ap.run(); r['Tout_C'] = ap.get(S + 'P\\Output\\TEMP_OUT\\MIXED') - K; r['wnet_unit'] = ap.unit(B + 'K1\\Output\\WNET')
    elif case == 'badname':
        base(ap, ['H2', ('MEOH', 'CH3OH')], 'PENG-ROB')
        ap.add_block('H', 'HEATER'); ap.connect('H', 'F(IN)', 'F'); ap.connect('H', 'P(OUT)', 'P')
        feed(ap, 'F', 25, 1, {'H2': 1, 'MEOH': 1}); ap.set(B + 'H\\Input\\TEMP', 373.15); ap.set(B + 'H\\Input\\PRES', 0)
        st = ap.run()
    r['trusted'] = st['trusted']; r['status'] = st['status']
print('RESULT ' + json.dumps(r))
'''.replace('HERE', repr(HERE))


def run_case(case):
    p = subprocess.run([sys.executable, '-c', CHILD, case], capture_output=True, text=True,
                       timeout=300, errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    line = [ln for ln in p.stdout.splitlines() if ln.startswith('RESULT ')]
    if not line:
        return None, (p.stdout + p.stderr)[-800:]
    return json.loads(line[-1][7:]), ''


def main():
    cases = sys.argv[1:] or list(EXPECT)
    lock = [sys.executable, os.path.join(HERE, 'aspen_lock.py')]
    subprocess.run(lock + ['acquire', 'selftest'], check=True)
    n_fail = 0
    try:
        for case in cases:
            r, err = run_case(case)
            if r is None:
                n_fail += 1
                print(f'FAIL {case}: no result\n{err}')
                continue
            if case != 'badname' and not r.get('trusted'):
                n_fail += 1
                print(f'FAIL {case}: run not trusted ({r.get("status")})')
                continue
            for label, expr, want, tol in EXPECT[case]:
                got = eval(expr, {}, {'r': r})
                ok = (got == want) if tol is None else abs(got - want) <= tol
                n_fail += not ok
                print(f'{"PASS" if ok else "FAIL"} {case}: {label} = {got!r} (expected {want!r}'
                      + ('' if tol is None else f' +/- {tol}') + ')')
    finally:
        subprocess.run(lock + ['release', 'selftest'])
    print(f'\n{n_fail} failure(s)')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
