"""Independent ideal-gas equilibrium check with Cantera, for cross-checking
Aspen RGibbs / REquil results.

    python equilibrium_check.py --T 850 --P 30 --feed CH4:1,H2O:3 --species CH4,H2O,H2,CO,CO2
    python equilibrium_check.py --T 250 --P 80 --feed H2:70,CO:20,CO2:7,CH4:3 \
        --species H2,CO,CO2,CH3OH,H2O --inert CH4
    python equilibrium_check.py --T 350 --P 30 --feed ... --species H2O,H2,CO,CO2 --inert CH4 --sweep-T 200,400,50

T in degC, P in bar(a), feed in any consistent molar units.  Prints wet and
dry mole fractions in %.

--species is the list of species allowed to react.  It is the whole point of
this script: an equilibrium solver with every species available returns the
thermodynamic minimum, which for most catalytic low-temperature processes is
methane (checked: methanol synthesis 250 C / 80 bar gives 0 % methanol and
46 % CH4; methanol steam reforming gives 71 % CH4 dry; shift at 350 C gives
86 % CH4).  Real catalysts are selective.  Restrict --species to what the
catalyst actually makes, and pass feed species that only ride along as
--inert (they keep their moles and dilute the mixture).

Thermo comes from gri30.yaml (species data valid to 3500 K; Cantera
extrapolates silently above that, so use --thermo nasa_gas.yaml for hot
systems).  Ideal gas only: above ~30 bar Aspen's PENG-ROB result differs by a
few points (methanol synthesis at 80 bar: 24.2 % ideal vs 26.9 % PR).
"""
import argparse
import warnings

import cantera as ct

warnings.filterwarnings('ignore')
INERT_CARRIER = 'AR'  # inert species are carried as argon-like moles, then renamed


def parse_feed(s):
    out = {}
    for item in s.split(','):
        k, v = item.split(':')
        out[k.strip()] = float(v)
    return out


def solve(T_C, P_bar, feed, species, inert, thermo):
    lib = {s.name: s for s in ct.Species.list_from_file(thermo)}
    missing = [s for s in species if s not in lib]
    if missing:
        raise SystemExit(f'species not in {thermo}: {missing}')
    names = list(dict.fromkeys(species + ([INERT_CARRIER] if inert else [])))
    gas = ct.Solution(thermo='ideal-gas', species=[lib[n] for n in names])
    X = {k: v for k, v in feed.items() if k not in inert}
    unknown = [k for k in X if k not in species]
    if unknown:
        raise SystemExit(f'feed species {unknown} are neither in --species nor --inert')
    n_inert = sum(feed.get(k, 0) for k in inert)
    if n_inert:
        X[INERT_CARRIER] = X.get(INERT_CARRIER, 0) + n_inert
    gas.TPX = T_C + 273.15, P_bar * 1e5, X
    gas.equilibrate('TP')
    x = dict(zip(gas.species_names, gas.X))
    if inert:
        carried = x.pop(INERT_CARRIER, 0.0)
        for k in inert:  # split the carrier back by feed share
            x[k] = carried * feed.get(k, 0) / n_inert
    return {k: v for k, v in x.items() if v > 1e-9}


def report(T_C, P_bar, x):
    dry = {k: v for k, v in x.items() if k != 'H2O'}
    s = sum(dry.values())
    order = lambda d: sorted(d.items(), key=lambda t: -t[1])
    print(f'T {T_C:g} C  P {P_bar:g} bar | wet % ' + ', '.join(f'{k} {100 * v:.2f}' for k, v in order(x))
          + ' | dry % ' + ', '.join(f'{k} {100 * v / s:.2f}' for k, v in order(dry)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--T', type=float, required=True, help='degC')
    ap.add_argument('--P', type=float, required=True, help='bar(a)')
    ap.add_argument('--feed', required=True, help='e.g. CH4:1,H2O:3')
    ap.add_argument('--species', required=True, help='species allowed to react, comma separated')
    ap.add_argument('--inert', default='', help='feed species carried as inert, comma separated')
    ap.add_argument('--thermo', default='gri30.yaml', help='gri30.yaml (<=3500 K) or nasa_gas.yaml (<=6000 K)')
    ap.add_argument('--sweep-T', default='', help='start,stop,step in degC')
    a = ap.parse_args()
    feed = parse_feed(a.feed)
    species = [s.strip() for s in a.species.split(',') if s.strip()]
    inert = [s.strip() for s in a.inert.split(',') if s.strip()]
    temps = [a.T]
    if a.sweep_T:
        t0, t1, dt = (float(v) for v in a.sweep_T.split(','))
        temps = [t0 + i * dt for i in range(int(round((t1 - t0) / dt)) + 1)]
    for T in temps:
        report(T, a.P, solve(T, a.P, feed, species, inert, a.thermo))


if __name__ == '__main__':
    main()
