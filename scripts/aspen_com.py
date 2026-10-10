"""Thin driver for Aspen Plus through the in-process COM server.

Checked on Aspen Plus V11 (37.0): the out-of-process ProgID
'Apwn.Document.37.0' hung in Dispatch, while 'Apwn.Document.IP' (in-process)
opened, ran, exported and saved normally.  Run probe_aspen_com.py first.

    from aspen_com import Aspen
    with Aspen(r'E:\\work\\model.bkp') as ap:          # copy of the user's file
        ap.set(r'\\Data\\Blocks\\R101\\Input\\CONV\\1', 0.83)
        ap.run()
        print(ap.get(r'\\Data\\Blocks\\R101\\Output\\QCALC'), ap.unit(r'...'))
        ap.export('rep', r'E:\\work\\model_run1')       # -> model_run1.rep
        print(ap.warnings())                           # Control Panel text
        ap.save_as(r'E:\\work\\model_run1.bkp')

    python aspen_com.py tree model.bkp "\\Data\\Blocks\\R101" 3   # browse names
    python aspen_com.py scan model.bkp "<input path>" 0.8 0.85 0.9 -- "<out path>" ...

Facts that cost time to find out:
- InitFromArchive2 opens .bkp only.  A hand-written .inp fails with
  "Unable to open file" when the batch engine has no license, because the
  .inp translation runs through that engine.  Get the first .bkp by opening
  the .inp once in the GUI, or build the model through COM (add_components / add_block / connect).
- InitNew2 starts in ENG units (25 means 25 F, 1 means 1 psia, flows in
  lbmol/hr) and only defines ENG, MET and SI; METCBAR does not exist in a
  blank document.  Call set_units('MET') first: K, atm, kmol/hr, cal/sec.
  Check unit() on anything you set before trusting it.
- Results are not reloaded from a .bkp; run() again after opening.
- Export codes: 1 bkp, 2 rep, 3 sum, 4 inp, 6 cpm (empty under COM).
  Aspen appends the extension itself, so pass the path without one.
- The run history (<name>.his next to the saved file, or the engine's work
  dir) contains the full Control Panel warning text.
- One document per Python process: after Close(), a second Dispatch of the
  in-process server in the same process fails with "operation not
  supported".  Run each model (or each case batch) in its own subprocess.
- The process holds the single license seat until Close(); the context
  manager closes it even on error.  Do not run while a GUI session is open.
"""
import glob
import os
import re
import sys
import time

EXPORT = {'bkp': 1, 'rep': 2, 'sum': 3, 'inp': 4}
UOSSTAT = {8: 'ok', 10: 'completed with warnings'}  # observed values; others: read warnings()


class Aspen:
    def __init__(self, bkp=None, progid='Apwn.Document.IP'):
        import pythoncom
        import win32com.client as w
        pythoncom.CoInitialize()
        self.doc = w.Dispatch(progid)
        if bkp:
            self.path = os.path.abspath(bkp)
            self.doc.InitFromArchive2(self.path)
        else:
            self.path = None
            self.doc.InitNew2()
        self.doc.SuppressDialogs = 1  # no GUI in-process; setting Visible raises
        self.tree = self.doc.Tree

    # context manager: always release the license seat
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        try:
            self.doc.Close()
        except Exception:
            pass

    # ------------------------------------------------------------------ data
    def node(self, path):
        n = self.tree.FindNode(path)
        if n is None:
            raise KeyError(f'no node {path}; browse with tree()')
        return n

    def get(self, path, default=None):
        n = self.tree.FindNode(path)
        return default if n is None else n.Value

    def set(self, path, value):
        self.node(path).Value = value

    def unit(self, path):
        try:
            return self.node(path).UnitString
        except Exception:
            return ''

    def children(self, path):
        return [e.Name for e in self.node(path).Elements]

    def tree_dump(self, path='\\Data', depth=2, _indent=0):
        """Print node names and values to discover variable names (QCALC, HX_DUTY ...)."""
        n = self.node(path)
        try:
            elems = list(n.Elements)
        except Exception:
            elems = []
        for e in elems:
            p = path + '\\' + e.Name
            try:
                v = e.Value
            except Exception:
                v = ''
            print('  ' * _indent + e.Name + ('' if v in (None, '') else f' = {v} {self.unit(p)}'))
            if depth > 1:
                try:
                    self.tree_dump(p, depth - 1, _indent + 1)
                except Exception:
                    pass

    # ------------------------------------------------------------------- run
    def set_units(self, unit_set='MET'):
        """Blank documents know ENG / MET / SI only; .bkp from the GUI may carry more."""
        self.set(r'\Data\Setup\Global\Input\INSET', unit_set)
        self.set(r'\Data\Setup\Global\Input\OUTSET', unit_set)

    def run(self):
        t = time.time()
        self.doc.Engine.Run2()
        code = self.get(r'\Data\Results Summary\Run-Status\Output\UOSSTAT2')
        return {'status_code': code, 'status': UOSSTAT.get(code, 'check warnings()'),
                'seconds': round(time.time() - t, 1)}

    def export(self, kind, path_without_ext):
        self.doc.Export(EXPORT[kind], os.path.abspath(path_without_ext))
        return os.path.abspath(path_without_ext) + '.' + kind

    def save_as(self, bkp):
        self.doc.SaveAs(os.path.abspath(bkp))
        self.path = os.path.abspath(bkp)

    def warnings(self):
        """Warning/error paragraphs from the newest .his next to the model."""
        d = os.path.dirname(self.path) if self.path else os.getcwd()
        his = sorted(glob.glob(os.path.join(d, '*.his')), key=os.path.getmtime)
        if not his:
            return []
        txt = open(his[-1], encoding='latin-1').read()
        return [m.group(0).strip() for m in
                re.finditer(r'\n +\*+ +(?:SEVERE |TERMINAL )?(?:WARNING|ERROR)[^\n]*(?:\n {6,}[^\n*]+)*', txt)]

    # ------------------------------------------------------------- build helpers
    def add_components(self, *ids):
        """ids as (alias, databank_name) or plain names."""
        comp = self.node(r'\Data\Components\Specifications\Input\TYPE')
        n0 = len(list(comp.Elements))
        for i, c in enumerate(ids):
            alias, dbname = (c, c) if isinstance(c, str) else c
            comp.Elements.InsertRow(0, n0 + i)
            comp.Elements.LabelNode(0, n0 + i)[0].Value = alias
            self.set(r'\Data\Components\Specifications\Input\DBNAME1' + '\\' + alias, dbname)

    def add_block(self, name, model):
        self.node(r'\Data\Blocks').Elements.Add(f'{name}!{model}')

    def connect(self, block, port, stream):
        """port examples: 'F(IN)', 'P(OUT)', 'V(OUT)', 'L(OUT)'; stream is created if missing."""
        if self.tree.FindNode('\\Data\\Streams\\' + stream) is None:
            self.node(r'\Data\Streams').Elements.Add(stream)
        self.node(f'\\Data\\Blocks\\{block}\\Ports\\{port}').Elements.Add(stream)


def _cli():
    cmd, bkp = sys.argv[1], sys.argv[2]
    with Aspen(bkp) as ap:
        if cmd == 'tree':
            ap.tree_dump(sys.argv[3] if len(sys.argv) > 3 else '\\Data',
                         int(sys.argv[4]) if len(sys.argv) > 4 else 2)
        elif cmd == 'scan':
            # scan <bkp> <input path> v1 v2 ... -- <out path> [<out path> ...]
            k = sys.argv.index('--')
            inp, vals, outs = sys.argv[3], sys.argv[4:k], sys.argv[k + 1:]
            print('value', *[o.split('\\')[-3] + ':' + o.split('\\')[-1] for o in outs], 'status', sep='\t')
            for v in vals:
                ap.set(inp, float(v))
                st = ap.run()
                print(v, *[ap.get(o) for o in outs], st['status'], sep='\t')
        else:
            raise SystemExit(__doc__)


if __name__ == '__main__':
    _cli()
