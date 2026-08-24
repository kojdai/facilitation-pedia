"""まだ書かれていない手法を、参照された回数の多い順に並べる。

記事を書いた人が `related` に挙げたのに、その手法のページがまだ無い——という参照が
80本以上ある。これは欠陥ではなく、**すでに「必要だ」と表明されている手法の一覧**である。
何を書けばよいか分からない、という貢献者にとって、いちばん確かな出発点になる。
"""
import collections
import os
import sys
from pathlib import Path

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")


def front(path):
    t = path.read_text(encoding="utf-8")
    return yaml.safe_load(t[4:t.index("\n---\n", 3) + 1]) or {}


def main():
    methods = {p.stem: front(p) for p in sorted(Path(DATA, "methods").glob("*.md"))}
    aliases = yaml.safe_load(open(os.path.join(DATA, "aliases.yaml"), encoding="utf-8")) or {}
    merges = yaml.safe_load(open(os.path.join(DATA, "merges.yaml"), encoding="utf-8")) or {}

    wanted = collections.defaultdict(list)
    for mid, m in methods.items():
        if mid in merges:
            continue
        for r in (m.get("related") or []):
            r = aliases.get(r, r)
            r = merges.get(r, r)
            if r not in methods and r != mid:
                wanted[r].append(mid)

    print(f"まだ書かれていない手法 {len(wanted)} 種（参照 {sum(len(v) for v in wanted.values())} 本）\n")
    print("参照された回数の多い順。数が多いほど、地図の穴として大きい。\n")
    for r, refs in sorted(wanted.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        names = ", ".join(methods[x].get("ja", x) for x in refs[:3])
        more = f" ほか{len(refs)-3}件" if len(refs) > 3 else ""
        print(f"  {len(refs):2}回  {r:34} ← {names}{more}")

    print("\n書き方は CONTRIBUTING.md を見てください。")
    print("「この手法は本当に要るのか」という判断から入って構いません。")
    print("不要だと思えば、参照元から related を外す提案でも立派な貢献です。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
