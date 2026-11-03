"""Write a decision file: python3 fill/mk.py '<json>'  (seq required)."""
import json, sys
d = json.loads(sys.argv[1])
open(f"fill/dec/{d['seq']:03d}.json", "w").write(json.dumps(d, ensure_ascii=False, indent=1))
