"""Parse an Aspen Plus .rep report into blocks, stream tables and run status.

Usage:
    PYTHONIOENCODING=utf-8 python parse_rep_template.py model.rep [out_dir]

Writes <out_dir>/<stem>_streams.csv (long format: stream, section, item, value)
and <out_dir>/<stem>_blocks.csv (block, model, item, value, unit), then prints
the PROBLEM STATUS text.  Import it instead when a project needs specific
numbers:

    from parse_rep_template import Rep
    rep = Rep('model.rep')
    rep.block_value('R101R', 'HEAT DUTY')          # -> 15.989
    rep.stream('PROD1-R')['STATE VARIABLES']['TEMP']  # -> 700.0
    rep.stream('PROD1-R')['COMPONENTS: MOLE FRAC']['CO']

Format notes (checked on V11 / VER 37.0):
- encoding is latin-1, not UTF-8;
- Fortran-style numbers drop the E: 7.6976-02, -2.3300+04;
- each page repeats a header and a section title; blocks that span pages
  reappear as "BLOCK:  X  MODEL: Y (CONTINUED)";
- the table of contents repeats every section and block name, so anchor on
  the real headings ("\n BLOCK:  " with one leading space, "\n STREAM ID "),
  not on the first occurrence of a section title.
"""
import csv
import os
import re
import sys

NUM = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[EeDd]?[-+]\d+)?'
PAGE_HDR = re.compile(r'\n ASPEN PLUS +PLAT:.*?PAGE +\d+ *\n[^\n]*\n[^\n]*\n')


def to_float(s):
    """'7.6976-02' -> 0.076976; '1.2D+03' -> 1200; '0.0' -> 0.0."""
    s = s.strip().replace('D', 'E').replace('d', 'E')
    m = re.fullmatch(r'([-+]?[\d.]+)([-+]\d+)', s)
    if m:
        s = m.group(1) + 'E' + m.group(2)
    return float(s)


class Rep:
    def __init__(self, path):
        raw = open(path, encoding='latin-1').read()
        self.text = PAGE_HDR.sub('\n', raw)
        self.blocks = self._split_blocks()
        self.streams = self._parse_streams()

    # ---------------------------------------------------------------- blocks
    def _split_blocks(self):
        # Real block headings start with exactly one space; TOC lines are
        # indented much further, so anchoring on "\n BLOCK:  " skips the TOC.
        body = self.text
        i = body.find('\n BLOCK:  ')
        j = body.find('\n STREAM ID ', i)
        body = body[i:j] if i >= 0 and j > i else body
        parts = re.split(r'\n BLOCK:  (\S+)\s+MODEL: (\S+)', body)
        blocks = {}
        for k in range(1, len(parts), 3):
            name, model, txt = parts[k], parts[k + 1], parts[k + 2]
            b = blocks.setdefault(name, {'model': model, 'text': ''})
            b['text'] += txt
        return blocks

    def block_value(self, block, label):
        """First number after `label` in the block text (label is a regex).

        Labels as printed in the RESULTS part, e.g. 'HEAT DUTY', 'CALCULATED
        HEAT DUTY', 'OUTLET TEMPERATURE', 'VAPOR FRACTION', 'NET WORK REQUIRED'.
        Units sit between the label and the number and are skipped.
        """
        b = self.blocks.get(block)
        if not b:
            return None
        m = re.search(label + r'[ A-Z/()\-*]*?\s(' + NUM + r')\s', b['text'])
        return to_float(m.group(1)) if m else None

    def block_results(self, block):
        """All 'LABEL  UNIT  number' lines in the block's RESULTS part."""
        b = self.blocks.get(block)
        if not b:
            return []
        txt = b['text']
        # RESULTS / OVERALL RESULTS (HEATX) / ZONE RESULTS all count
        r = re.search(r'\*\*\*  [A-Z ]*RESULTS  \*\*\*', txt)
        if not r:
            return []  # e.g. MIXER prints only the balance and input data
        row = re.compile(r' {2,8}([A-Z][A-Z0-9 ,.\-/()%]*?)\s{2,}(?:(\S+)\s+)?(' + NUM + r')')
        out = []
        for ln in txt[r.start():].split('\n'):
            m = row.fullmatch(ln.rstrip())
            # skip multi-column tables (K-values, zone tables): numbers in label or unit
            if not m or re.search(r'\s' + NUM + r'(\s|$)', m.group(1) + ' ') or \
                    (m.group(2) and re.fullmatch(NUM, m.group(2))):
                continue
            out.append((m.group(1).strip(), to_float(m.group(3)), m.group(2) or ''))
        return out

    # --------------------------------------------------------------- streams
    def _parse_streams(self):
        streams = {}
        for page in re.split(r'\n STREAM ID ', self.text)[1:]:
            lines = page.split('\n')
            ids = lines[0].split()
            section = ''
            for ln in lines[1:]:
                if not ln.strip():
                    continue
                if ln.startswith(' ') and not ln.startswith('   ') and ln.rstrip().endswith(':') or \
                        re.match(r' [A-Z][A-Z ]+:\s*[A-Z/ ]*$', ln):
                    section = ln.strip().rstrip(':').strip()
                    continue
                if re.match(r' (BLOCK:|\*|PROBLEM STATUS)', ln) or 'SECTION' in ln:
                    break
                toks = ln.split()
                vals = toks[-len(ids):]
                try:
                    nums = [to_float(v) for v in vals]
                except ValueError:
                    continue  # FROM/TO/PHASE rows and other text rows
                item = ' '.join(toks[:-len(ids)])
                for sid, v in zip(ids, nums):
                    streams.setdefault(sid, {}).setdefault(section, {})[item] = v
        return streams

    def stream(self, sid):
        return self.streams.get(sid, {})

    # ---------------------------------------------------------------- status
    def status(self):
        i = self.text.rfind('PROBLEM STATUS SECTION')
        if i < 0:
            return ''
        lines = [ln.strip(' *') for ln in self.text[i:].split('\n') if ln.strip(' *')]
        return '\n'.join(lines[1:])


def main():
    path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(path))
    stem = os.path.splitext(os.path.basename(path))[0]
    rep = Rep(path)
    with open(os.path.join(out_dir, stem + '_streams.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['stream', 'section', 'item', 'value'])
        for sid, secs in rep.streams.items():
            for sec, items in secs.items():
                for item, v in items.items():
                    w.writerow([sid, sec, item, v])
    with open(os.path.join(out_dir, stem + '_blocks.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['block', 'model', 'item', 'value', 'unit'])
        for name, b in rep.blocks.items():
            for item, v, unit in rep.block_results(name):
                w.writerow([name, b['model'], item, v, unit])
    print(f'{len(rep.blocks)} blocks, {len(rep.streams)} streams -> {out_dir}')
    print(rep.status())


if __name__ == '__main__':
    main()
