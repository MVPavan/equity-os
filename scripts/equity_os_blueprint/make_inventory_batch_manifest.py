#!/usr/bin/env python3
"""Per-kind manifests for real recording; excludes any component with a non-CLEAN artifact and DISP-R-1."""
import importlib.util, json, pathlib, subprocess, sys
REPO=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("recorder", REPO/"scripts/equity_os_blueprint/record_inventory_review.py")
rec=importlib.util.module_from_spec(spec); spec.loader.exec_module(rec)
kind=sys.argv[1]; out=pathlib.Path(sys.argv[2])
def dirty():
    o=subprocess.run(["git","-C",str(REPO),"status","--short","--untracked-files=all"],capture_output=True,text=True,check=True).stdout
    s=set()
    for l in o.splitlines():
        if l.strip():
            e=l[3:].strip()
            if " -> " in e: e=e.split(" -> ",1)[1]
            s.add(e.strip('"'))
    return s
ledger=REPO/rec.LEDGER_RELPATH; rows=rec.load_rows(ledger)
entries=[]; paths=set(); excluded=[]
for row in rows:
    if row["kind"]!=kind or row["component_id"]=="DISP-R-1": continue
    cid=row["component_id"]; group=[]
    ok=True
    for rt in rec.applicable_review_types(row):
        rel=f"{rec.INVENTORY_ARTIFACT_ROOT}/{cid}/{rt}-r0.md"; tgt=REPO/rel
        if not tgt.exists(): ok=False; excluded.append((cid,f"missing {rt}")); break
        p=rec.parse_verdict_artifact(tgt)
        if p["verdict"]!=rec.VERDICT_CLEAN: ok=False; excluded.append((cid,f"{rt}={p['verdict']}")); break
        e={"component_id":cid,"review_type":rt,"artifact_path":rel,"artifact_sha256":rec.sha256_file(tgt)}
        for f in rec.ARTIFACT_FIELDS:
            if f not in ("component_id","review_type"): e[f]=p[f]
        group.append((e,rel))
    if ok:
        for e,rel in group: entries.append(e); paths.add(rel)
base=sorted(dirty()-paths-{rec.LEDGER_RELPATH})
m={"schema":rec.MANIFEST_SCHEMA,"batch_id":f"real-{kind}","ledger_prehash_sha256":rec.sha256_file(ledger),"baseline_dirty_paths":base,"reviews":entries}
out.write_text(json.dumps(m,indent=2,sort_keys=True)+"\n")
print(f"{kind}: {len(entries)} reviews over {len({e['component_id'] for e in entries})} components; excluded {excluded}; baseline dirty {base}")
