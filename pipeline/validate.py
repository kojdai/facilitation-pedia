"""data/ の書き方を検査して、**人に読める言葉で**間違いを伝える。

このリポジトリには、プログラミングを仕事にしていない方が編集に来る。
Python のエラーをそのまま見せると、それだけで「自分には無理だ」と離脱してしまう。
だからここでは traceback を出さず、「どのファイルの・何が・どう違うか・どう直すか」を書く。
"""
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

STATUSES = {"Draft", "Verified", "Needs_Review"}


class Problem:
    def __init__(self, path, msg, hint=None):
        self.path, self.msg, self.hint = path, msg, hint

    def show(self):
        rel = os.path.relpath(self.path, os.path.dirname(HERE))
        print(f"\n  ✗ {rel}")
        print(f"    {self.msg}")
        if self.hint:
            print(f"    → {self.hint}")


def read_front_matter(path, problems):
    """Markdown を (frontmatter, 本文) に割る。壊れていたら None を返す。"""
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        problems.append(Problem(
            path, "ファイルの1行目が `---` で始まっていません。",
            "ファイルの先頭は必ず `---` の行から始めてください。"
            "その次の行から情報欄（frontmatter）が続きます。"))
        return None, None
    try:
        end = text.index("\n---\n", 3)
    except ValueError:
        problems.append(Problem(
            path, "情報欄の終わりを示す `---` の行が見つかりません。",
            "情報欄は `---` で始めて `---` で閉じます。閉じる側が消えていないか確認してください。"))
        return None, None
    try:
        front = yaml.safe_load(text[4:end + 1]) or {}
    except yaml.YAMLError as e:
        line = getattr(getattr(e, "problem_mark", None), "line", None)
        where = f"（{line + 2} 行目のあたり）" if line is not None else ""
        problems.append(Problem(
            path, f"情報欄の書き方が読み取れませんでした{where}。",
            "よくある原因は3つです。"
            "①「: 」のうしろに値がない ②行頭の空白がずれている "
            "③文の中に「:」があるのに引用符で囲っていない（例 `ja: \"対話: その本質\"`）"))
        return None, None
    if not isinstance(front, dict):
        problems.append(Problem(path, "情報欄が「項目: 値」の形になっていません。"))
        return None, None
    return front, text[end + 5:].lstrip("\n")


def load_yaml(name, problems):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        line = getattr(getattr(e, "problem_mark", None), "line", None)
        where = f"（{line + 1} 行目のあたり）" if line is not None else ""
        problems.append(Problem(path, f"YAML の書き方が読み取れませんでした{where}。",
                                "行頭の空白のずれと、閉じ忘れの引用符をまず疑ってください。"))
        return None


def check_records(subdir, id_field, required, problems):
    from pathlib import Path
    records = {}
    for path in sorted(Path(os.path.join(DATA, subdir)).glob("*.md")):
        front, body = read_front_matter(str(path), problems)
        if front is None:
            continue
        rid = front.get(id_field)
        stem = path.stem
        if not rid:
            problems.append(Problem(str(path), f"`{id_field}` が書かれていません。",
                                    f"情報欄に `{id_field}: {stem}` の行を足してください。"))
            continue
        if rid != stem:
            problems.append(Problem(
                str(path), f"`{id_field}: {rid}` がファイル名 `{stem}.md` と一致しません。",
                "この2つは必ず同じにします。片方だけ変えるとリンクが切れます。"))
        for f in required:
            if not front.get(f):
                problems.append(Problem(str(path), f"`{f}` が空です。",
                                        "この項目は地図の表示に必要です。"))
        st = front.get("status")
        if st and st not in STATUSES:
            problems.append(Problem(
                str(path), f"`status: {st}` は使えない値です。",
                f"使えるのは {' / '.join(sorted(STATUSES))} のいずれかです。"
                "監修が済んでいないものは Draft のままにしてください。"))
        if not (body or "").strip():
            problems.append(Problem(str(path), "本文が空です。",
                                    "情報欄を閉じる `---` の下に、解説の本文を書きます。"))
        records[rid] = front
    return records


def main():
    problems = []
    methods = check_records("methods", "id", ["ja", "desc"], problems)
    people = check_records("people", "id", ["name"], problems)
    concepts = load_yaml("concepts.yaml", problems) or []
    disciplines = load_yaml("disciplines.yaml", problems) or []
    for name in ("relations.yaml", "concept-lineage.yaml", "discipline-lineage.yaml",
                 "facilitation.yaml", "roadmap.yaml", "institutions.yaml",
                 "books.yaml", "merges.yaml", "meta.yaml"):
        load_yaml(name, problems)

    concept_ids = {c.get("id") for c in concepts if isinstance(c, dict)}
    disc_ids = {d.get("id") for d in disciplines if isinstance(d, dict)}

    # 参照が生きているか
    for mid, m in methods.items():
        path = os.path.join(DATA, "methods", f"{mid}.md")
        for pid in (m.get("people") or []):
            if pid not in people:
                problems.append(Problem(
                    path, f"`people` に書かれた `{pid}` という人物が見つかりません。",
                    f"data/people/ に {pid}.md があるか確認してください。"
                    "人物ページを先に作るか、綴りを直します。"))
        cid = m.get("concept")
        if cid and cid not in concept_ids:
            problems.append(Problem(
                path, f"`concept: {cid}` という中核概念は存在しません。",
                "data/concepts.yaml にある id から選んでください。"))
        for d in (m.get("disciplines") or []):
            if d not in disc_ids:
                problems.append(Problem(
                    path, f"`disciplines` の `{d}` という源流は存在しません。",
                    "data/disciplines.yaml にある id から選んでください。"))

    for c in concepts:
        if not isinstance(c, dict):
            continue
        for d in (c.get("disciplines") or []):
            if d not in disc_ids:
                problems.append(Problem(os.path.join(DATA, "concepts.yaml"),
                                        f"概念 `{c.get('id')}` の源流 `{d}` は存在しません。"))
        a = c.get("anchor_method")
        if a and a not in methods:
            problems.append(Problem(
                os.path.join(DATA, "concepts.yaml"),
                f"概念 `{c.get('id')}` の代表手法 `{a}` が見つかりません。",
                f"data/methods/{a}.md を作るか、別の手法を指してください。"))

    print(f"検査しました： 手法 {len(methods)} / 人物 {len(people)} / "
          f"中核概念 {len(concept_ids)} / 源流 {len(disc_ids)}")
    if not problems:
        print("\n✅ 問題は見つかりませんでした。")
        return 0
    print(f"\n直してほしいところが {len(problems)} 件あります。")
    for p in problems[:40]:
        p.show()
    if len(problems) > 40:
        print(f"\n  ...ほか {len(problems) - 40} 件")
    print("\n困ったら Issue で聞いてください。誰かが必ず答えます。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
