"""出典の充足状況を調べる。

なぜ要るか：この地図は CC0（誰でも自由に使ってよい）で公開する。
つまり「使ってよい」と告げた内容を、知らない誰かがそのまま使う。
出典のない記述は、その人にまで誤りを渡すことになる。

また出典は、読む人がこの地図を越えて先へ進むための入口でもある。
地図は目的地ではなく通り道なので、ここが空だと片道で終わってしまう。
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ATLAS = os.path.join(os.path.dirname(HERE), "dist", "atlas.json")
TIER_LABEL = {1: "中核", 2: "主要", 3: "派生"}


def main():
    d = json.load(open(ATLAS, encoding="utf-8"))

    print("=== 出典の充足状況 ===\n")
    print(f"{'':8} {'全体':>6} {'出典あり':>8} {'充足率':>7}")
    for label, key in (("手法", "methods"), ("人物", "people")):
        recs = d[key]
        have = [r for r in recs if (r.get("sources") or [])]
        print(f"{label:8} {len(recs):6} {len(have):8} {len(have)/len(recs)*100:6.0f}%")

    print("\n=== 重要度ごと（手法） ===")
    for tier in (1, 2, 3):
        recs = [m for m in d["methods"] if m.get("tier") == tier]
        have = [m for m in recs if (m.get("sources") or [])]
        if recs:
            print(f"  tier{tier}（{TIER_LABEL[tier]}）  {len(have):3}/{len(recs):3}"
                  f"  {len(have)/len(recs)*100:5.0f}%")

    missing1 = [m for m in d["methods"] if m.get("tier") == 1 and not (m.get("sources") or [])]
    if missing1:
        print(f"\n=== 出典がない中核手法 {len(missing1)} 件（ここから埋めるのが最も効く） ===")
        for m in missing1:
            print(f"  {m['id']:28} {m['ja']}")

    print("\n=== 監修状態 ===")
    for label, key in (("手法", "methods"), ("人物", "people")):
        st = collections.Counter(r.get("status") for r in d[key])
        total = len(d[key])
        parts = "  ".join(f"{k} {v}（{v/total*100:.0f}%）" for k, v in st.most_common())
        print(f"  {label}: {parts}")

    print("\n※ Draft は監修が済んでいないことを示す。公開時にどう見せるかは別途決める。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
