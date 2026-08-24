"""概念・源流・機関を1レコード1ファイルへ（一度きりの移行）。

GUI（Sveltia CMS）のリレーション欄は「コレクション」を指す。単一 YAML の中の配列は
指せないため、参照される側はすべて1レコード1ファイルに揃える必要がある。
PR の差分が読みやすくなる（38件の配列を1行だけ直した差分は読めない）という利点もある。

説明文（desc）は本文へ移す。人が書き直すのは主にここなので、frontmatter に押し込めず
本文として開いておく。
"""
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# (元ファイル, 出力ディレクトリ, 本文にするフィールド)
TARGETS = [
    ("concepts.yaml", "concepts", "desc"),
    ("disciplines.yaml", "disciplines", "desc"),
    ("institutions.yaml", "institutions", "desc"),
]


def write_record(path, front, body):
    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False,
                        default_flow_style=False, width=100).rstrip("\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n" + fm + "\n---\n\n" + (body or "").rstrip("\n") + "\n")


def main():
    for src, subdir, body_field in TARGETS:
        path = os.path.join(DATA, src)
        if not os.path.exists(path):
            print(f"  {src} は既に移行済み")
            continue
        records = yaml.safe_load(open(path, encoding="utf-8")) or []
        outdir = os.path.join(DATA, subdir)
        os.makedirs(outdir, exist_ok=True)
        for r in records:
            body = r.pop(body_field, "") or ""
            front = {k: v for k, v in r.items() if v not in (None, [], "")}
            write_record(os.path.join(outdir, f"{r['id']}.md"), front, body)
        os.remove(path)
        print(f"  {src:20} → data/{subdir}/ ({len(records)} 件)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
