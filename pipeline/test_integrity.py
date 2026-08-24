"""生成物の関係が壊れていないことを確かめる。

正本では片側だけ書けばよく、向きの補完・別名の解決・統廃合の転送は build.py が行う。
その保証が効いているかを、生成物の側で検査する。
移行前は 2,506本中 1,317本（53%）が片側だけ、89本が切れ、10本が自己参照だった。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.join(os.path.dirname(HERE), "dist", "atlas.json")


def main():
    d = json.load(open(ATLAS, encoding="utf-8"))
    ids = {m["id"] for m in d["methods"]}
    rel = {m["id"]: set(m.get("related") or []) for m in d["methods"]}
    people = {p["id"] for p in d["people"]}

    fails = []
    broken = [(a, b) for a, v in rel.items() for b in v if b not in ids]
    oneway = [(a, b) for a, v in rel.items() for b in v if a not in rel.get(b, set())]
    selfref = [a for a, v in rel.items() if a in v]
    ghost = [(m["id"], p) for m in d["methods"] for p in (m.get("people") or []) if p not in people]
    tomb = [m["id"] for m in d["methods"] if m.get("merged_into") and m.get("related")]
    nobook = [(m["id"], b) for m in d["methods"] for b in (m.get("books") or []) if not b.get("title")]

    for label, bad in (("存在しない手法への参照", broken),
                       ("片側だけの関連（両側に張られていない）", oneway),
                       ("自分自身への参照", selfref),
                       ("存在しない人物への参照", ghost),
                       ("統廃合された手法が関連を持っている", tomb),
                       ("書名のない書籍参照", nobook)):
        if bad:
            fails.append(f"  ✗ {label}: {len(bad)} 件  例 {bad[:3]}")

    total = sum(len(v) for v in rel.values())
    if fails:
        print("❌ 関係が壊れています")
        print("\n".join(fails))
        return 1
    print(f"✅ 関係は健全（手法間の関連 {total} 本・切れ0・片側0・自己参照0）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
