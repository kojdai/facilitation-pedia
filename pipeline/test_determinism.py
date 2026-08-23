"""ビルド結果がレコードの並び順に依存しないことを確かめる。

なぜ要るか：概念の割り当ては related グラフを伝播して決まる。実装を誤ると
「パスの途中で確定したものが後続に影響する」形になり、**ファイルを1つ足しただけで
無関係な手法の分類が動く**。誰でもファイルを追加できるリポジトリでは、これは
レビューできない差分を生む事故になる。だから並びを入れ替えても同じ結果になることを検査する。
"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build as B  # noqa: E402


def derive(seed=None):
    data, patch = B.load_data()
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(data['methods'])
        rng.shuffle(data['people'])
    B.apply_concepts(data, patch)
    B.remap_people_disciplines(data)
    # 並びの違いそのものは比較対象にしない（id をキーに畳む）
    return {
        'methods': {m['id']: (m.get('concept'), m.get('tier'), tuple(m.get('disciplines') or []))
                    for m in data['methods']},
        'people': {p['id']: tuple(p.get('disciplines') or []) for p in data['people']},
    }


def main():
    base = derive()
    failures = 0
    for seed in (1, 2, 3, 42, 12345):
        got = base if seed is None else derive(seed)
        for kind in ('methods', 'people'):
            diff = [k for k in base[kind] if base[kind][k] != got[kind].get(k)]
            if diff:
                failures += 1
                print(f"  ✗ seed={seed} {kind}: {len(diff)} 件が並び順で変化 例={diff[:5]}")
    if failures:
        print(f"\n❌ 並び順に依存している（{failures} 件）")
        return 1
    print(f"✅ 並び順に依存しない（手法 {len(base['methods'])} / 人物 {len(base['people'])} を5通りの並びで検査）")
    return 0


if __name__ == '__main__':
    sys.exit(main())
