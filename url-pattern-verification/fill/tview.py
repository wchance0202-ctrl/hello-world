"""Template-filtered structure view: drop links that appear on >=40% of the same host's entries."""
import sys, json
from collections import Counter, defaultdict
sys.path.insert(0, 'fill')
from links import links
from structs import key
R = json.load(open('fill/rows.json'))
E = {}
for d in ['output/round3', 'batch2/output/round3']:
    for e in json.load(open(d + '/entries.json')):
        if e['kind'] == 'path_entry': E[e['entry_id']] = e
a, b = int(sys.argv[1]), int(sys.argv[2])
rows = [r for r in R if a <= r['seq'] <= b]
hosts = {E[r['entry_ids'][0]]['host'] for r in rows}
ids = [k for k, e in E.items() if e['host'] in hosts]
L = links(ids)
for r in rows:
    eid = r['entry_ids'][0]; h = E[eid]['host']
    sib = [k for k in ids if E[k]['host'] == h]
    cnt = Counter(u for k in sib for u in L[k])
    keep = [u for u in L[eid] if len(sib) < 3 or cnt[u] < max(2, 0.4 * len(sib))]
    g = defaultdict(list)
    for u in keep: g[key(u)].append(u)
    print(f"#{r['seq']} {eid} {r['url']} kept {len(keep)}/{len(L[eid])} (host entries {len(sib)})")
    for k, us in sorted(g.items(), key=lambda kv: -len(kv[1]))[:6]:
        print(f"    {len(us):>4} {k[:95]}  e.g. {sorted(us)[0][:95]}")
