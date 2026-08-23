"""【履歴】xlsx からの移行が無損失だったことを確かめた記録（2026-08-23・一度きり）。

結果：**未説明の差分 0 件**。説明済みの差分は2件のみで、いずれも旧パイプラインのバグが
直ったもの（apply_method_content を導出の後に実行していたため、人物の源流が
著者記載のフォールバックのままになっていた）。

このスクリプトは**もう通らない**。移行のあとに2つの変更を意図して入れたため：
  1. 概念割当ての伝播を順序非依存にした（旧は並び順で結果が変わった）
  2. 源流トークンを正式な id へ正規化した（旧は od / psych などの旧名が残っていた）
CI には入れない。移行時点の検証手順を残すためだけに置いている。

--- 以下、当時の説明 ---
移行が無損失かを、元の atlas.json と突き合わせて確かめる（一度きりの検証用）。

概念割当ての伝播（build.py step 4）はレコードの並び順に依存するため、
比較の前に**元と同じ並び**に揃えてから導出を掛ける。これで並び順の影響を消し、
「移行でデータが失われていないか」だけを見る。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build as B  # noqa: E402

OLD = "/home/dkojima/dev/helping/dev/src/data/atlas.json"
IGNORE = {"related_flags"}

# 説明済みの差分（移行によって直った旧パイプラインのバグ）。
# 旧 main() は apply_method_content（手法へ people を補う上書き）を
# remap_people_disciplines の**後**に実行していた。そのため導出の時点では
# 手法に人物が紐づいておらず、この2人は著者記載のフォールバック値になっていた。
# 移行後は上書きが各レコードへ畳み込まれているので、手法から正しく導出される。
EXPLAINED = {
    ("people", "aedmond", "disciplines"),
    ("people", "dbohm", "disciplines"),
}


def main():
    old = json.load(open(OLD, encoding="utf-8"))
    data, patch = B.load_data()

    # 元の並びへ揃える
    for key in ("methods", "people"):
        order = {x["id"]: i for i, x in enumerate(old[key])}
        data[key].sort(key=lambda r: order.get(r["id"], 10**6))

    B.apply_concepts(data, patch)
    B.remap_people_disciplines(data)
    B.inject_discipline_lineage(data, patch)
    disc_ids = {d["id"] for d in data["disciplines"]}
    data["facilitation_inflows"] = [e for e in patch["facilitation_inflows"]
                                    if e.get("from_id") in disc_ids]
    data["roadmap_books"] = {k: v for k, v in patch["roadmap_books"].items() if k in disc_ids}
    data["facilitation_applications"] = patch["facilitation_applications"]

    diffs, explained = [], []
    for key in sorted(set(old) | set(data)):
        o, n = old.get(key), data.get(key)
        if isinstance(o, list) and o and isinstance(o[0], dict) and "id" in o[0]:
            oi = {x["id"]: x for x in o}
            ni = {x["id"]: x for x in n}
            if set(oi) != set(ni):
                diffs.append(f"{key}: id集合 欠={sorted(set(oi)-set(ni))[:5]} 増={sorted(set(ni)-set(oi))[:5]}")
            for i in sorted(set(oi) & set(ni)):
                for f in sorted((set(oi[i]) | set(ni[i])) - IGNORE):
                    a, b = oi[i].get(f), ni[i].get(f)
                    if isinstance(a, str):
                        a = a.strip()
                    if isinstance(b, str):
                        b = b.strip()
                    # 「空リスト」と「未設定」は旧データでは xlsx のセルの書き方の
                    # 違いでしかなく、意味の差がない。正規化して比較する。
                    if a in (None, []) and b in (None, []):
                        continue
                    if (key, i, f) in EXPLAINED:
                        explained.append(f"{key}[{i}].{f}: 旧={a} / 新={b}")
                        continue
                    if a != b:
                        diffs.append(f"{key}[{i}].{f}: 旧={str(a)[:70]!r} / 新={str(b)[:70]!r}")
        else:
            j = lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False)
            if j(o) != j(n):
                diffs.append(f"{key}: 一致しない")

    if explained:
        print(f"=== 説明済みの差分 {len(explained)} 件（旧パイプラインのバグが直ったもの） ===")
        for e in explained:
            print("  ", e)
    print(f"=== 未説明の差分 {len(diffs)} 件 ===")
    for d in diffs[:30]:
        print("  ", d)
    if len(diffs) > 30:
        print(f"   ...他 {len(diffs)-30} 件")
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
