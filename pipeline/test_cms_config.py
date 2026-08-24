"""編集画面（GUI）の設定が、実データの項目をすべて宣言できているかを確かめる。

Sveltia CMS は **設定に宣言されていない項目を、保存時に捨てる**。
つまり data/ に項目を足して config.yml に足し忘れると、
誰かが GUI で1文字直しただけで、その項目が静かに消える。

しかも消えたことは PR の差分を注意深く見ないと気づけない。
プログラミングをしない人が編集する前提なので、気づける人がいない前提で守る必要がある。
"""
import collections
import os
import sys
from pathlib import Path

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def front(path):
    t = path.read_text(encoding="utf-8")
    return yaml.safe_load(t[4:t.index("\n---\n", 3) + 1]) or {}


def main():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "admin", "config.yml"), encoding="utf-8"))
    failures = []
    for col in cfg["collections"]:
        folder = col.get("folder")
        if not folder:
            continue
        declared = {f["name"] for f in col["fields"]}
        actual = collections.Counter()
        for p in Path(ROOT, folder).glob("*.md"):
            actual.update(front(p).keys())
        missing = sorted(set(actual) - declared)
        if missing:
            failures.append((col["name"], missing))
        print(f"  {col['name']:14} 実データ {len(actual):2} 項目 / 宣言 {len(declared):2} 項目")

    if failures:
        print("\n❌ 編集画面で保存すると消えてしまう項目があります")
        for name, missing in failures:
            print(f"  ✗ {name}: {missing}")
            print(f"    → admin/config.yml の {name} コレクションに、この項目を足してください")
        return 1
    print("\n✅ 実データの項目はすべて編集画面に宣言されています")
    return 0


if __name__ == "__main__":
    sys.exit(main())
