"""書籍を正規化する（一度きりの移行）。

これまで書籍は各手法の中にコピーとして埋め込まれており、同じ本が最大9箇所に複製され、
そのうち24件で書誌情報が食い違っていた（著者名の表記ゆれ・出版社の欠落など）。
コピーが枝分かれして劣化する典型で、1冊＝1レコードにすれば構造的に起きなくなる。

ただし埋め込みには `reason`（この手法にとってなぜこの本か）が含まれ、これは
**同じ本でも手法ごとに違う**（34件で実際に違っていた）。つまり書籍の属性ではなく
「手法と書籍の関係」の属性なので、参照側に残す：

    books:
    - ref: 世界はシステムで動く      # ← 書籍レコードへの参照
      note: システム思考の全体像をつかむ入門書   # ← この手法にとっての意味
"""
import collections
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
BOOKS_DIR = os.path.join(DATA, "books")

# ファイル名に使えない文字だけを落とす（書名はそのまま id にする＝差分が読める）
ILLEGAL = re.compile(r'[/:\\?*"<>|]')


def slug(title):
    return ILLEGAL.sub("", title).strip()


def read_front_matter(path):
    text = open(path, encoding="utf-8").read()
    end = text.index("\n---\n", 3)
    return yaml.safe_load(text[4:end + 1]) or {}, text[end + 5:].lstrip("\n")


def write_record(path, front, body):
    fm = yaml.safe_dump(front, allow_unicode=True, sort_keys=False,
                        default_flow_style=False, width=100).rstrip("\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n" + fm + "\n---\n\n" + (body or "").rstrip("\n") + "\n")


def merge_biblio(entries):
    """同じ書名の複数のコピーから、最も情報の多い書誌を組み立てる。

    値が食い違う場合は多数決。それでも割れたら、最初に現れたものを採る。
    どちらにせよ人の確認が要るので、食い違いは呼び出し側へ返す。
    """
    out, conflicts = {}, []
    for field in ("author", "publisher", "year", "level", "lang", "author_id"):
        vals = [e[field] for e in entries if e.get(field) not in (None, "")]
        if not vals:
            continue
        counts = collections.Counter(map(str, vals))
        if len(counts) > 1:
            conflicts.append((field, dict(counts)))
        best = counts.most_common(1)[0][0]
        out[field] = next(v for v in vals if str(v) == best)
    if any(e.get("essential") for e in entries):
        out["essential"] = True
    return out, conflicts


def main():
    from pathlib import Path

    # 1) 全ての書籍レコードを書名で束ねる
    grouped = collections.defaultdict(list)
    method_files = sorted(Path(os.path.join(DATA, "methods")).glob("*.md"))
    method_books = {}
    for p in method_files:
        front, body = read_front_matter(str(p))
        refs = []
        for b in (front.get("books") or []):
            if not isinstance(b, dict) or not b.get("title"):
                continue
            grouped[b["title"]].append(b)
            ref = {"ref": slug(b["title"])}
            note = b.get("reason") or b.get("note")
            if note:
                ref["note"] = note
            refs.append(ref)
        method_books[str(p)] = (front, body, refs)

    table = yaml.safe_load(open(os.path.join(DATA, "books.yaml"), encoding="utf-8")) or []
    for b in table:
        if b.get("title"):
            grouped[b["title"]].append(b)

    # 2) 1冊＝1ファイルで書き出す
    os.makedirs(BOOKS_DIR, exist_ok=True)
    conflicts_report = []
    for title, entries in sorted(grouped.items()):
        biblio, conflicts = merge_biblio(entries)
        if conflicts:
            conflicts_report.append((title, conflicts))
        front = {"id": slug(title), "title": title}
        front.update(biblio)
        # 書籍そのものについての説明（books.yaml 側の note）は本文へ。
        # 手法ごとの reason は参照側に残すので、ここには入れない。
        body = next((e["note"] for e in entries if e.get("note") and "id" in e), "")
        write_record(os.path.join(BOOKS_DIR, f"{slug(title)}.md"), front, body)

    # 3) 手法側を参照に置き換える
    for path, (front, body, refs) in method_books.items():
        if refs:
            front["books"] = refs
        else:
            front.pop("books", None)
        write_record(path, front, body)

    print(f"書籍レコード      {len(grouped)} 件を data/books/ へ")
    print(f"手法からの参照    {sum(len(r) for _, _, r in method_books.values())} 本")
    print(f"書誌が食い違った  {len(conflicts_report)} 件（人の確認が要る）")
    for title, cs in conflicts_report[:6]:
        print(f"    {title[:40]}")
        for field, counts in cs:
            print(f"        {field}: {counts}")
    if len(conflicts_report) > 6:
        print(f"    ...ほか {len(conflicts_report)-6} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
