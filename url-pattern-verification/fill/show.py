import json,sys
R=json.load(open('fill/structs.json'))
a,b=int(sys.argv[1]),int(sys.argv[2]); top=int(sys.argv[3]) if len(sys.argv)>3 else 6
for r in R:
    if not a<=r['seq']<=b: continue
    print(f"#{r['seq']} {r['entry_id']} {r['url']} | {r['status'][:6]} p{r['pages']} L{r['n_links']} pre={r['prefix']} sm={int(r['has_sitemap'])} hostE={r['same_host_entries']}")
    for s in r['structs'][:top]:
        print(f"    {s['n']:>4} {'IN ' if s['in_prefix'] else '   '}oth{len(s['other_entries_with_key'])} sm{s['sitemap_n']:<6} {s['key'][:90]}  e.g. {s['samples'][0][:90]} [{s['texts'][0]}]")
