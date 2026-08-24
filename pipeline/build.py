"""data/ のテキスト正本から dist/atlas.json を生成する。

正本は data/ 配下の Markdown（frontmatter）と YAML であり、**dist/atlas.json は生成物**。
生成物を直接編集しても次のビルドで消えるので、必ず data/ を直すこと。

このファイルの大半は「導出」＝人が書かなくてよい情報を機械が埋める処理である：
  ・各手法がどの中核概念に属し、重要度 tier がいくつか（概念の anchor / seeds と related グラフから）
  ・各手法・各人物がどの源流に連なるか（概念経由で導出。手で書くと必ずずれる）
  ・統廃合された手法の転送先

依存: PyYAML のみ（`pip install pyyaml`）。
"""
import os
import re
import json
import sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'dist', 'atlas.json')

# Columns that hold JSON-encoded arrays/objects in the spreadsheet.
LIST_COLS = {
    'People': ['disciplines', 'works', 'achievements', 'framework_dimensions', 'sources'],
    'Methods': ['disciplines', 'people', 'related', 'books', 'framework_dimensions', 'sources'],
}
FLOAT_COLS = {'People': ['pos_x', 'pos_y']}
BOOL_COLS = {'Methods': ['essential'], 'Books': ['essential']}

# High-confidence id corrections for broken references (verified against the
# people/method id list: each target exists, the source is a clear typo/alias).
ID_ALIASES = {
    'kegan': 'rkegan',                       # Robert Kegan
    'lewin': 'klewin',                       # Kurt Lewin
    'gergen': 'kgergen',                     # Kenneth Gergen
    'gagne': 'rgagne',                       # Robert Gagne
    'freire': 'pfreire',                     # Paulo Freire
    'scharmer': 'oscharmer',                 # Otto Scharmer
    'world_cafe': 'wcafe',                   # World Cafe
    'social_construction': 'social_constructionism',
    'sa_authorship': 'selfauthorship',       # Self-Authorship theory
    # --- method.related typos / id drift (each target verified to exist) ---
    'vygotsky': 'lvygotsky',                 # Lev Vygotsky
    'spiral_dynamics': 'spiraldyn',
    'social_identity': 'social_identity_theory',
    'family_systems': 'internal_family_systems',
    'nonviolent_communication': 'nvc',
    'agile': 'agile_facilitation',
    # --- 重複人物レコードの統合（重複id → Verified側の正規id）---
    'psenge': 'senge',                       # Peter Senge
    'dschon': 'schon',                       # Donald Schön
    'dkolb': 'kolb',                         # David Kolb
    'cargyr': 'argyris',                     # Chris Argyris
    'jmacy': 'macy',                         # Joanna Macy
}

# Discipline-token ids that legitimately appear as relation endpoints: these are
# field-to-field intellectual-lineage edges, not broken person/method refs.
DISCIPLINE_TOKENS = {
    'edu_philosophy', 'pragmatism', 'humanistic', 'learning_sci', 'lab_method',
    'drama_edu', 'dialogue', 'org_dev', 'knowledge', 'systems',
    'adult_dev', 'theory_u', 'integral',
}

# Canonical discipline master, keyed by the tokens that people/methods/relations
# actually use. The spreadsheet shipped a parallel, partially-mismatched taxonomy
# (od/alt/adt/...) that required a lossy remap in the app; this replaces it so the
# data is internally consistent (items, lineage edges and master all share ids).
# 源流タイポロジー（メタ・ナラティブレビューで再導出した13の研究伝統）。
# 最上位＝WS・ファシリテーションの直下に並ぶ源流。詳細は pipeline/META_NARRATIVE_REVIEW.md。
DISCIPLINES = [
    {"id": "edu_philosophy", "ja": "教育哲学・批判教育学・教育人間学", "en": "Educational Philosophy & Critical Pedagogy",
     "hex": "#8a1030", "desc": "教育の目的と人間形成を問う源流。デューイの民主主義、フレイレの批判教育学（意識化）、ブーバーの対話哲学、ビースタの『よい教育』、日本の教育人間学が、対話と解放の認識論的土台を与える。"},
    {"id": "pragmatism", "ja": "プラグマティズム・省察的実践", "en": "Pragmatism & Reflective Practice",
     "hex": "#b1001e", "desc": "経験と省察を学びの中心に据える。デューイの『為すことによって学ぶ』、ショーンの『行為の中の省察』、コルブの経験学習サイクル、コルトハーヘンのリアリスティック・アプローチが、経験学習とリフレクションの母体となる。"},
    {"id": "humanistic", "ja": "人間性心理学・パーソンセンタード", "en": "Humanistic & Person-Centered Psychology",
     "hex": "#e6002d", "desc": "自己実現と無条件の肯定的関心を核とする第三勢力心理学。マズロー、ロジャーズのパーソンセンタード、ジェンドリンのフォーカシングが、エンカウンター・傾聴・アサーション・NVC・コンパッションへと展開する。"},
    {"id": "learning_sci", "ja": "学習科学・教育工学・ID", "en": "Learning Sciences & Instructional Design",
     "hex": "#ef4055", "desc": "人はどう学び、学習環境をどう設計するか。ヴィゴツキー／ピアジェの構成主義、ガニェ・ライゲルースのインストラクショナルデザイン、レイヴ＆ウェンガーの状況的学習、学習科学とハッティの教育効果研究、研修転移・HPIを含む。"},
    {"id": "lab_method", "ja": "集団力学・ラボラトリー方式", "en": "Group Dynamics & Laboratory Method",
     "hex": "#ff7090", "desc": "クルト・レヴィンの場の理論とアクションリサーチを源流に、NTLのTグループ（ラボラトリー方式の体験学習）が誕生。『いま・ここ』の集団過程からの体験学習が、ファシリテーションの直接の母体となった（日本では南山大学が継承）。"},
    {"id": "drama_edu", "ja": "演劇・ドラマ教育（応用インプロ）", "en": "Drama Education & Applied Improvisation",
     "hex": "#ffb066", "desc": "身体性・即興・創発を場づくりに応用する。スポーリンとジョンストンの即興演劇、ボアールの被抑圧者の演劇、教育現場の演劇的手法（高尾隆ほか）、プレイバックシアターやSPTが、創造性と協働を引き出す。"},
    {"id": "dialogue", "ja": "対話・ホールシステム・社会構成主義", "en": "Dialogue, Whole-System & Social Construction",
     "hex": "#d62388", "desc": "言葉が現実を構成するという社会構成主義（ガーゲン）を土台に、ボームのダイアログ、アイザックスのダイアローグ、ワールド・カフェ・OST・サークル・Art of Hosting、オープンダイアローグなど、大人数の集合的対話を扱う。"},
    {"id": "org_dev", "ja": "組織開発（OD）", "en": "Organization Development",
     "hex": "#f57e00", "desc": "応用行動科学を基盤に、組織のプロセスへ介入して健全性とパフォーマンスを高める。シャインのプロセス・コンサルテーション、アージリスの組織学習、クーパーライダーのAI、ブッシュ＆マーシャクの対話型ODが合流する、現代実践の中心。"},
    {"id": "knowledge", "ja": "知識創造", "en": "Knowledge Creation",
     "hex": "#c98a00", "desc": "野中郁次郎・竹内弘高の組織的知識創造論。暗黙知と形式知が変換され続けるSECIモデルと『場（ba）』、実践知（フロネシス）に基づくワイズリーダーシップが、日本発の経営知として源流に加わる。"},
    {"id": "systems", "ja": "システム思考・複雑系", "en": "Systems Thinking & Complexity",
     "hex": "#0a86a3", "desc": "事象を相互作用する全体として捉える。ベイトソン、フォレスターのシステムダイナミクス、メドウズ、センゲの学習する組織、スノーデンのCynefinなど、サイバネティクスから複雑系までのシステム論の系譜。"},
    {"id": "adult_dev", "ja": "成人発達・変容", "en": "Adult Development & Transformation",
     "hex": "#6a3a8a", "desc": "成人以降の意味づけの構造が段階的に発達・変容する。ピアジェ／コールバーグの構成的発達、キーガンの成人発達、メジローの変容的学習、トルバートのアクション・インクワイアリが、垂直的成長と発達指向型組織の地図を描く。"},
    {"id": "theory_u", "ja": "U理論・プレゼンシング", "en": "Theory U & Presencing",
     "hex": "#8a5acf", "desc": "オットー・シャーマーらが提唱する、出現する未来からリードする変容の理論。開いて手放し迎え入れるU字のプロセスと、身体性を伴うソーシャル・プレゼンシング・シアター（SPT）が、システム変容の方法論を与える。"},
    {"id": "integral", "ja": "インテグラル・スパイラル", "en": "Integral Theory & Spiral Dynamics",
     "hex": "#b07ad8", "desc": "ケン・ウィルバーのインテグラル理論（AQAL＝全象限・全レベル）と、グレイブス／ベックのスパイラル・ダイナミクスが、多様な発達段階と世界観を統合的に地図化するメタ理論を提供する。"},
]

# 旧分野トークン（source.xlsx 由来）。新タイポロジーへの移行で関係エンドポイントとして無効化される。
OLD_DISC = {'philo', 'psych', 'edutec', 'social', 'mgmt', 'od', 'system', 'dialogue', 'improv', 'dev'}
# 概念未割当の残差・人物のフォールバック用：旧→新の単純リネーム（分割は概念側で吸収）。
DISC_RENAME = {
    'philo': 'edu_philosophy', 'psych': 'humanistic', 'edutec': 'learning_sci',
    'social': 'lab_method', 'mgmt': 'org_dev', 'od': 'org_dev',
    'system': 'systems', 'dialogue': 'dialogue', 'improv': 'drama_edu', 'dev': 'adult_dev',
}
# 分割元の人物で、所属手法からの自動導出が誤りやすい理論家を明示割当て（名寄せ前の重複IDも両方記載）。
PEOPLE_DISC_OVERRIDE = {
    'nonaka': 'knowledge', 'oscharmer': 'theory_u', 'kwilber': 'integral', 'cgraves': 'integral',
    'dschon': 'pragmatism', 'schon': 'pragmatism', 'dkolb': 'pragmatism', 'kolb': 'pragmatism',
    'pfreire': 'edu_philosophy', 'jmacy': 'dialogue', 'macy': 'dialogue', 'kgergen': 'dialogue',
    'psenge': 'systems', 'senge': 'systems', 'dsnowden': 'systems', 'nbateson': 'systems', 'bateson': 'systems',
    'amaslow': 'humanistic', 'crogers': 'humanistic', 'mseligman': 'humanistic', 'cryff': 'humanistic',
    'edeci': 'humanistic', 'rryan': 'humanistic', 'mcsikszent': 'humanistic',
    'rkegan': 'adult_dev', 'wtorbert': 'adult_dev', 'jmezirow': 'adult_dev', 'mezirow': 'adult_dev',
    'jloevinger': 'adult_dev', 'lkohlberg': 'adult_dev', 'jpiaget': 'adult_dev', 'kfischer': 'adult_dev',
    'mknowles': 'learning_sci', 'lvygotsky': 'learning_sci', 'hgardner': 'learning_sci', 'bbloom': 'learning_sci',
    'rgagne': 'learning_sci', 'creigeluth': 'learning_sci', 'dmerrill': 'learning_sci',
    'ttsumura': 'lab_method', 'klewin': 'lab_method',
}


def remap_people_disciplines(data):
    """人物の源流を新タイポロジーへ。明示割当て→所属手法の主概念から導出→旧トークンのリネーム。"""
    from collections import Counter
    concept_disc = {c['id']: list(c.get('disciplines') or []) for c in data['concepts']}
    tally = {p['id']: Counter() for p in data['people']}
    for m in data['methods']:
        cd = concept_disc.get(m.get('concept'))
        if not cd:
            continue
        for pid in (m.get('people') or []):
            if pid in tally:
                tally[pid][cd[0]] += 1
    for p in data['people']:
        if p['id'] in PEOPLE_DISC_OVERRIDE:
            p['disciplines'] = [PEOPLE_DISC_OVERRIDE[p['id']]]
        elif tally[p['id']]:
            p['disciplines'] = [tally[p['id']].most_common(1)[0][0]]
        else:
            p['disciplines'] = [DISC_RENAME.get(t, t) for t in (p.get('disciplines') or [])]


def inject_discipline_lineage(data, patch):
    """旧分野間エッジ（無効トークン）を落とし、patches の discipline_lineage を関係として注入。"""
    data['relations'] = [
        r for r in data['relations']
        if r.get('from_id') not in OLD_DISC and r.get('to_id') not in OLD_DISC
    ]
    valid = {d['id'] for d in data['disciplines']}
    added = 0
    for e in patch.get('discipline_lineage', []):
        if e.get('from_id') in valid and e.get('to_id') in valid:
            data['relations'].append({
                'id': f"dl_{e['from_id']}_{e['to_id']}",
                'from_id': e['from_id'], 'to_id': e['to_id'],
                'type': 'discipline_lineage', 'kind': None, 'note': e.get('note', ''),
            })
            added += 1
    return added


def clean(v):
    """Normalise a raw cell value."""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.lstrip("'")          # strip Excel text-marker apostrophe
        v = v.strip()
        if v == '':
            return None
    return v


def parse_json_cell(v):
    if v is None:
        return None
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return v


def parse_bool(v):
    if v is None:
        return False
    return str(v).strip().lower() in ('1', 'true', 'yes', '⭐')


def parse_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def build_records(sheet, rows):
    out = []
    for raw in rows_to_dicts(rows):
        rec = {k: clean(v) for k, v in raw.items()}
        for col in LIST_COLS.get(sheet, []):
            rec[col] = parse_json_cell(rec.get(col))
        for col in FLOAT_COLS.get(sheet, []):
            rec[col] = parse_float(rec.get(col))
        for col in BOOL_COLS.get(sheet, []):
            rec[col] = parse_bool(rec.get(col))
        if rec.get('id') or rec.get('key'):
            out.append(rec)
    return out


def apply_aliases(data):
    """Repair known id typos across every reference field. Returns a count."""
    n = 0

    def fix(x):
        nonlocal n
        if x in ID_ALIASES:
            n += 1
            return ID_ALIASES[x]
        return x

    for r in data['relations']:
        r['from_id'] = fix(r['from_id'])
        r['to_id'] = fix(r['to_id'])
    for m in data['methods']:
        if m.get('related'):
            m['related'] = [fix(x) for x in m['related']]
        if m.get('people'):
            m['people'] = [fix(x) for x in m['people']]
    for b in data.get('books', []):
        if b.get('author_id'):
            b['author_id'] = fix(b['author_id'])
    # 重複人物レコードの統合：別名キー＝重複idのレコードを削除（参照は上で正規idへ寄せ済み）。
    canon = {p['id'] for p in data['people']}
    before = len(data['people'])
    data['people'] = [p for p in data['people']
                      if not (p['id'] in ID_ALIASES and ID_ALIASES[p['id']] in canon)]
    n += before - len(data['people'])
    return n


def load_patches():
    """Read patches.json once (shared by apply_patches and apply_concepts)."""
    if not os.path.exists(PATCHES):
        return {}
    with open(PATCHES, encoding='utf-8') as f:
        return json.load(f)


# 手法レコードの既定値（source.xlsx の列に合わせる）。patches の methods_add は
# 必要な項目だけ書けばよく、残りはここで補われる。
METHOD_DEFAULTS = {
    'id': None, 'ja': None, 'en': None, 'icon': None, 'disciplines': None,
    'people': None, 'desc': None, 'detail_markdown': None, 'related': None,
    'books': None, 'essential': False, 'framework_dimensions': None,
    'sources': None, 'status': 'Draft', 'last_verified_at': None,
    'last_modified_at': None, 'related_flags': None, 'created_at': None,
}
INSTITUTION_DEFAULTS = {
    'id': None, 'name': None, 'country': None, 'year': None, 'desc': None,
    'url': None, 'status': 'Draft', 'last_verified_at': None, 'last_modified_at': None,
}


def _merge_add(collection, records, defaults):
    """Append patch-authored records (filling defaults), skipping existing ids."""
    existing = {r['id'] for r in collection}
    added = []
    for rec in records:
        if not rec.get('id') or rec['id'] in existing:
            continue
        merged = dict(defaults)
        merged.update(rec)
        collection.append(merged)
        existing.add(rec['id'])
        added.append(merged)
    return added


def apply_patches(data, patch):
    """Merge curated supplementary records from patches.json. Returns a summary."""
    if not patch:
        return {}
    existing = {p['id'] for p in data['people']}
    added = [p for p in patch.get('people_add', []) if p['id'] not in existing]
    data['people'].extend(added)
    # source.xlsx に無い手法・機関を patches 側で追加する（people_add と同型）。
    # ここで足すことで、後段の概念割当て・tier付与・書籍整形にそのまま乗る。
    methods_added = _merge_add(data['methods'], patch.get('methods_add', []), METHOD_DEFAULTS)
    inst_added = _merge_add(data['institutions'], patch.get('institutions_add', []),
                            INSTITUTION_DEFAULTS)
    drop = set(patch.get('relations_drop', []))
    before = len(data['relations'])
    data['relations'] = [r for r in data['relations'] if r.get('id') not in drop]
    # relation_notes: override the note on a relation, keyed "from_id>to_id".
    # Lets review corrections to 分野間の影響 (discipline-lineage) edges live in
    # patches.json instead of the binary source.xlsx.
    notes = patch.get('relation_notes', {})
    note_n = 0
    if notes:
        for r in data['relations']:
            key = f"{r.get('from_id')}>{r.get('to_id')}"
            if key in notes:
                r['note'] = notes[key]
                note_n += 1
    return {'people_added': len(added), 'methods_added': len(methods_added),
            'institutions_added': len(inst_added),
            'relations_dropped': before - len(data['relations']),
            'relation_notes': note_n}


# Each discipline token maps to a representative concept, used as the fallback
# bucket when a method cannot be placed via its anchor/seed/related graph.
DISC_DEFAULT_CONCEPT = {
    'philo': 'dewey_experientialism', 'psych': 'constructivist_learning',
    'edutec': 'instructional_design', 'social': 'group_dynamics',
    'od': 'action_research', 'mgmt': 'learning_organization',
    'system': 'systems_thinking', 'dialogue': 'whole_system_approach',
    'improv': 'applied_improvisation', 'dev': 'adult_development',
}


def _disc_hex(token):
    for d in DISCIPLINES:
        if d['id'] == token:
            return d['hex']
    return '#9a8e84'


def apply_concepts(data, patch):
    """Build the 中核概念 (core-concept) layer and assign each method a
    concept + importance tier (1=中核手法 / 2=主要手法 / 3=派生・関連).

    Resolution order: anchor(=tier1) and seed(=tier2) come from patches; the
    long tail is bucketed by propagating along the `related` graph, then by a
    discipline-default fallback. Duplicate methods are merged into a canonical
    record (demoted to tier3, `related` references redirected). Returns a summary.
    """
    concepts_in = patch.get('concepts', [])
    if not concepts_in:
        data.setdefault('concepts', [])
        data.setdefault('concept_lineage', [])
        return {}

    method_ix = {m['id']: m for m in data['methods']}
    valid_concept = {c['id'] for c in concepts_in}
    merges = {d: c for d, c in patch.get('methods_merge', {}).items()
              if d in method_ix and c in method_ix}

    # 1) concept master records (colour follows the primary discipline)
    inst_ids = {i['id'] for i in data['institutions']}
    concept_inst = {cid: [i for i in insts if i in inst_ids]
                    for cid, insts in patch.get('concept_institutions', {}).items()}
    data['concepts'] = [{
        'id': c['id'], 'ja': c['ja'], 'en': c['en'],
        'disciplines': c.get('disciplines') or [],
        'hex': _disc_hex((c.get('disciplines') or ['od'])[0]),
        'anchor_method': c.get('anchor_method'),
        'desc': c.get('desc', ''),
        'institutions': concept_inst.get(c['id'], []),
    } for c in concepts_in]

    # 2) redirect duplicate references in every method's `related` list
    for m in data['methods']:
        if m.get('related'):
            seen, red = set(), []
            for x in m['related']:
                x = merges.get(x, x)
                if x not in seen:
                    seen.add(x)
                    red.append(x)
            m['related'] = red

    # 3) seed assignments: anchors (tier1) then seeds (tier2)
    assign = {}  # method_id -> (concept_id, tier)
    pinned_n = 0
    pinned_unknown = []
    for c in concepts_in:
        a = c.get('anchor_method')
        if a in method_ix:
            assign[a] = (c['id'], 1)
    for c in concepts_in:
        for s in c.get('seeds', []):
            if s in method_ix and s not in assign:
                assign[s] = (c['id'], 2)

    # 3.5) 人が明示した分類（frontmatter の concept）を、自動推測より優先して確定する。
    #      anchor（その概念の代表手法）だけは概念側の定義が勝つ＝地図の骨格を守るため。
    for m in data['methods']:
        pin = m.get('_pinned_concept')
        if not pin or m['id'] in merges:
            continue
        if pin not in valid_concept:
            pinned_unknown.append((m['id'], pin))
            continue
        if assign.get(m['id'], (None, None))[1] == 1:
            continue  # anchor は動かさない
        assign[m['id']] = (pin, 2 if m.get('essential') else 3)
        pinned_n += 1

    # 4) propagate along the related graph (a few passes for transitivity)
    #
    # ※ 各パスは「パス開始時点のスナップショット」だけを見て決め、確定はパスの最後にまとめて行う。
    #    こうしないと、同じパスの中で先に確定したものが後続の判定に影響し、
    #    **レコードの並び順で結果が変わる**（＝ファイルを1つ足すと無関係な手法の分類が動く）。
    #    OSS として誰でもファイルを追加できるようにする以上、ここは順序非依存でなければならない。
    for _ in range(5):
        snapshot = dict(assign)
        pending = {}
        for m in data['methods']:
            mid = m['id']
            if mid in snapshot or mid in merges:
                continue
            tally = {}
            for r in (m.get('related') or []):
                if r in snapshot:
                    cid = snapshot[r][0]
                    tally[cid] = tally.get(cid, 0) + 1
            if tally:
                # 同数のときは概念 id の辞書順で決める（安定した結果にするため）
                best = max(tally, key=lambda k: (tally[k], k))
                pending[mid] = (best, 2 if m.get('essential') else 3)
        if not pending:
            break
        assign.update(pending)

    # 5) discipline-default fallback for whatever is still unplaced
    for m in data['methods']:
        mid = m['id']
        if mid in assign or mid in merges:
            continue
        cid = DISC_DEFAULT_CONCEPT.get((m.get('disciplines') or [None])[0])
        if cid in valid_concept:
            assign[mid] = (cid, 2 if m.get('essential') else 3)

    # 6) duplicates follow their canonical record, demoted to tier3
    for dup, canon in merges.items():
        assign[dup] = (assign.get(canon, (None, None))[0], 3)

    # 7) write concept/tier onto methods
    for m in data['methods']:
        m.pop('_pinned_concept', None)
        cid, tier = assign.get(m['id'], (None, 2 if m.get('essential') else 3))
        m['concept'] = cid
        m['tier'] = tier
        if m['id'] in merges:
            m['merged_into'] = merges[m['id']]

    # 7.5) 源流の唯一の真実＝概念→源流。各手法の disciplines をその概念の
    # disciplines から導出する（source.xlsx の旧分野トークンに依存しない）。
    # 概念未割当の残差のみ、旧トークンを新源流へリネームして温存。
    concept_disc = {c['id']: list(c.get('disciplines') or []) for c in data['concepts']}
    for m in data['methods']:
        cd = concept_disc.get(m.get('concept'))
        if cd:
            m['disciplines'] = list(cd)
        else:
            m['disciplines'] = [DISC_RENAME.get(t, t)
                                for t in (m.get('disciplines') or [])]

    # 8) people -> institutions (系譜/学派)
    people_ix = {p['id']: p for p in data['people']}
    inst_links = 0
    for pid, ov in patch.get('people_overrides', {}).items():
        p = people_ix.get(pid)
        if p and ov.get('institutions'):
            p['institutions'] = ov['institutions']
            inst_links += 1

    # 9) concept -> concept intellectual lineage (理論間の影響)
    data['concept_lineage'] = [
        e for e in patch.get('concept_lineage', [])
        if e.get('from_id') in valid_concept and e.get('to_id') in valid_concept
    ]

    by_tier = {}
    for m in data['methods']:
        by_tier[m.get('tier')] = by_tier.get(m.get('tier'), 0) + 1
    return {
        'concepts': len(data['concepts']),
        'tier1': by_tier.get(1, 0), 'tier2': by_tier.get(2, 0), 'tier3': by_tier.get(3, 0),
        'pinned': pinned_n, 'pinned_unknown': pinned_unknown,
        'no_concept': sum(1 for m in data['methods'] if not m.get('concept')),
        'merged': len(merges), 'inst_links': inst_links,
        'concept_lineage': len(data['concept_lineage']),
    }


def apply_method_content(data, patch):
    """Override curated content (desc / detail_markdown / status / sources) on
    existing methods. Supports `detail_from`/`desc_from` to adopt another record's
    text without duplicating long strings in patches.json (used to promote the
    richer write-up from a merged duplicate onto the canonical record). Returns count.
    """
    overrides = patch.get('method_content', {})
    if not overrides:
        return 0
    mix = {m['id']: m for m in data['methods']}
    n = 0
    for mid, ov in overrides.items():
        m = mix.get(mid)
        if not m:
            continue
        if ov.get('detail_from') and mix.get(ov['detail_from']):
            m['detail_markdown'] = mix[ov['detail_from']].get('detail_markdown')
        if ov.get('desc_from') and mix.get(ov['desc_from']):
            m['desc'] = mix[ov['desc_from']].get('desc')
        for k in ('ja', 'en', 'icon', 'desc', 'detail_markdown', 'status', 'sources', 'people'):
            if k in ov:
                m[k] = ov[k]
        # spot-fix substrings without re-supplying the whole text (small corrections)
        if ov.get('detail_replace') and m.get('detail_markdown'):
            for a, b in ov['detail_replace'].items():
                m['detail_markdown'] = m['detail_markdown'].replace(a, b)
        n += 1
    return n


_JP_RE = re.compile(r'[ぁ-んァ-ヶー一-龥々〆ヵヶ]')


def _has_jp(s):
    return bool(_JP_RE.search(s or ''))


def _norm_title(t):
    """Normalise a book title for matching: lowercase, drop subtitle after the
    first ':'/'：'/'—', collapse whitespace, strip surrounding punctuation."""
    t = (t or '').strip()
    for sep in (':', '：', '—', ' - ', '–'):
        if sep in t:
            t = t.split(sep)[0]
            break
    t = re.sub(r'\s+', ' ', t).strip().strip('.,；;　').lower()
    return t


def apply_book_canon(data, patch):
    """Reorganise each method's embedded book lineup toward Japanese editions.

    patches.json `book_canon` maps an English/original title (any case, subtitle
    optional) to the curated Japanese edition/substitute
    {title, author, publisher, year, level?, note?}. Per method.books entry:
      - title matches a canon key  -> replaced by the Japanese edition
      - else, title is foreign (no JP chars) and unmapped -> dropped (untranslated)
      - else (already Japanese)     -> kept as-is
    Results are de-duplicated by title within each method. Returns a summary.
    """
    canon_raw = patch.get('book_canon', {})
    canon = {_norm_title(k): v for k, v in canon_raw.items() if not k.startswith('_')}
    adds = patch.get('method_books_add', {})
    replaced = dropped = kept = added = 0
    for m in data.get('methods', []):
        books = m.get('books') or []
        out, seen = [], set()
        for bk in books:
            if not isinstance(bk, dict):
                continue
            title = bk.get('title', '')
            hit = canon.get(_norm_title(title))
            if hit:
                nb = {'title': hit['title'], 'author': hit.get('author', bk.get('author', '')),
                      'year': hit.get('year', bk.get('year', ''))}
                if hit.get('publisher'):
                    nb['publisher'] = hit['publisher']
                if hit.get('note'):
                    nb['note'] = hit['note']
                lv = hit.get('level', bk.get('level'))
                if lv:
                    nb['level'] = lv
                if bk.get('essential'):
                    nb['essential'] = True
                replaced += 1
            elif not _has_jp(title):
                dropped += 1
                continue
            else:
                nb = bk
                kept += 1
            key = _norm_title(nb['title'])
            if key in seen:
                continue
            seen.add(key)
            out.append(nb)
        # curated per-method Japanese additions (fills lineups whose source books
        # were untranslated foreign works with no title-level mapping)
        for add in adds.get(m['id'], []):
            key = _norm_title(add.get('title', ''))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(dict(add))
            added += 1
        m['books'] = out
    return {'replaced': replaced, 'dropped': dropped, 'kept': kept,
            'added': added, 'canon_entries': len(canon)}


def apply_term_renames(data, patch):
    """Normalise terminology across all source-derived text (e.g. 自己著者性 ->
    セルフオーサーシップ). Lets a vocabulary change requested by the editor reach
    records that live in the binary source.xlsx and can't be hand-edited. Returns
    the number of replacements made.
    """
    renames = patch.get('term_rename', {})
    if not renames:
        return 0
    str_fields = ('ja', 'en', 'desc', 'detail_markdown', 'role', 'note', 'quote', 'school')
    list_fields = ('achievements', 'works')
    n = 0

    def sub(s):
        nonlocal n
        for a, b in renames.items():
            if a in s:
                n += s.count(a)
                s = s.replace(a, b)
        return s

    for coll in ('people', 'methods', 'relations', 'concepts', 'institutions', 'books'):
        for r in data.get(coll, []):
            for f in str_fields:
                if isinstance(r.get(f), str):
                    r[f] = sub(r[f])
            for f in list_fields:
                if isinstance(r.get(f), list):
                    r[f] = [sub(x) if isinstance(x, str) else x for x in r[f]]
    return n


def validate(data):
    people = {p['id'] for p in data['people']}
    methods = {m['id'] for m in data['methods']}
    disciplines = {d['id'] for d in data['disciplines']}
    nodes = people | methods
    report = []

    broken_rel = [
        (r['from_id'], r['to_id'], r.get('type'))
        for r in data['relations']
        if (r['from_id'] not in nodes and r['from_id'] not in DISCIPLINE_TOKENS)
        or (r['to_id'] not in nodes and r['to_id'] not in DISCIPLINE_TOKENS)
    ]
    lineage_rel = [
        r for r in data['relations']
        if r['from_id'] in DISCIPLINE_TOKENS and r['to_id'] in DISCIPLINE_TOKENS
    ]
    broken_related = sum(
        1 for m in data['methods'] for x in (m.get('related') or []) if x not in nodes
    )
    broken_people = sum(
        1 for m in data['methods'] for x in (m.get('people') or []) if x not in people
    )

    report.append(f"people:        {len(data['people'])}")
    report.append(f"methods:       {len(data['methods'])}")
    report.append(f"relations:     {len(data['relations'])}")
    report.append(f"disciplines:   {len(data['disciplines'])}")
    report.append(f"institutions:  {len(data['institutions'])}")
    report.append(f"books:         {len(data['books'])}")
    report.append("")
    p_md = sum(1 for p in data['people'] if (p.get('detail_markdown') or '').strip())
    m_md = sum(1 for m in data['methods'] if (m.get('detail_markdown') or '').strip())
    report.append(f"people detail_markdown filled:  {p_md}/{len(data['people'])}")
    report.append(f"methods detail_markdown filled: {m_md}/{len(data['methods'])}")
    report.append("")
    report.append(f"discipline-lineage relations (field->field): {len(lineage_rel)}")
    report.append(f"broken relation refs (person/method):        {len(broken_rel)}")
    for f, t, ty in broken_rel:
        report.append(f"    - {f} -> {t} [{ty}]")
    report.append(f"broken method.related refs: {broken_related}")
    report.append(f"broken method.people refs:  {broken_people}")
    return "\n".join(report), len(broken_rel)


def read_front_matter(path):
    """Markdown を (frontmatter dict, 本文) に割る。"""
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return {}, text
    end = text.index('\n---\n', 3)
    front = yaml.safe_load(text[4:end + 1]) or {}
    return front, text[end + 5:].lstrip('\n')


def load_yaml(name, default=None):
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return default if default is not None else {}
    with open(p, encoding='utf-8') as f:
        return yaml.safe_load(f) or (default if default is not None else {})


def load_records(subdir, body_field):
    """data/<subdir>/*.md を読み、本文を body_field へ入れて返す（id 順で安定させる）。"""
    from pathlib import Path
    out = []
    for p in sorted(Path(os.path.join(DATA, subdir)).glob('*.md')):
        front, body = read_front_matter(p)
        front[body_field] = body
        out.append(front)
    return out


def load_data():
    """テキスト正本を、旧パイプラインが期待する形（data, patch）に組み立てる。"""
    data = {
        'people':       load_records('people', 'detail_markdown'),
        'methods':      load_records('methods', 'detail_markdown'),
        'relations':    load_yaml('relations.yaml', []),
        'disciplines':  load_records('disciplines', 'desc'),
        'institutions': load_records('institutions', 'desc'),
        'books':        load_records('books', 'note'),
        'meta':         load_yaml('meta.yaml', {}),
    }
    fac = load_yaml('facilitation.yaml', {})
    data['_aliases'] = load_yaml('aliases.yaml', {}) or {}
    patch = {
        'concepts':                  load_records('concepts', 'desc'),
        'methods_merge':             load_yaml('merges.yaml', {}),
        'concept_lineage':           load_yaml('concept-lineage.yaml', []),
        'discipline_lineage':        load_yaml('discipline-lineage.yaml', []),
        'concept_institutions':      load_yaml('concept-institutions.yaml', {}),
        'facilitation_inflows':      fac.get('inflows', []),
        'facilitation_applications': fac.get('applications', []),
        'roadmap_books':             load_yaml('roadmap.yaml', {}),
        # 以下はテキスト移行の時点で各レコードへ畳み込み済み（もう上書き層は要らない）
        'people_overrides': {}, 'method_content': {}, 'book_canon': {},
        'term_rename': {}, 'people_add': [], 'methods_add': [], 'institutions_add': [],
    }
    # 欠けている既定値を補う（旧 METHOD_DEFAULTS / INSTITUTION_DEFAULTS と同じ役割）
    for m in data['methods']:
        for k, v in METHOD_DEFAULTS.items():
            m.setdefault(k, v() if callable(v) else v)
        # books は「無い」ではなく「空」で扱う（旧パイプラインと同じ。UI 側の分岐を減らす）
        m['books'] = m.get('books') or []
        # frontmatter に concept が書いてあれば「人が指定した分類」として退避する。
        # 自動割当ては related グラフの多数決という弱い推測なので、人の判断が上に立つ。
        m['_pinned_concept'] = m.pop('concept', None)
    # 関連手法（related）を整える。ここでやることは3つ：
    #   ① 別名を正式な id へ寄せる（aliases.yaml）
    #   ② 存在しない参照を落とす（推測で繋ぐと誤りを埋め込むので、繋がずに落とす）
    #   ③ **両側に張る**。正本では片側だけ書けばよい。
    #
    # ③ が要るのは、related が向きを持たない関係だから。人が両側に書く運用にすると
    # 必ず片側だけになる（移行前は 2,506本中 1,317本＝53% が片側だけだった）。
    # 意志で守らせるのではなく、機械が張れば構造的に揃う。
    aliases = data.pop('_aliases', {})
    # 統廃合された手法への参照も、ここで統合先へ寄せておく。
    # 後段（apply_concepts step 6）でも転送は行われるが、そこで書き換えると
    # 下の「両側に張る」が終わったあとになり、非対称と自己参照が生まれる。
    merges = patch.get('methods_merge', {}) or {}
    method_ids = {m['id'] for m in data['methods']}
    missing_related = []
    resolved = {}
    for m in data['methods']:
        # 統廃合された手法は「墓標」であり、関係は統合先が引き受ける。
        # ここを張り直しの対象に含めると、墓標→X の参照が X→墓標 として復活し、
        # 後段の転送で X→X（自己参照）に化ける。
        if m['id'] in merges:
            m['related'] = []
            resolved[m['id']] = set()
            continue
        out = []
        for r in (m.get('related') or []):
            r = aliases.get(r, r)
            seen_merge = set()
            while r in merges and r not in seen_merge:
                seen_merge.add(r)
                r = merges[r]
            if r == m['id']:
                continue                       # 自分自身は落とす
            if r not in method_ids:
                missing_related.append((m['id'], r))
                continue
            out.append(r)
        resolved[m['id']] = set(out)
    for a, targets in list(resolved.items()):  # 両側に張る
        for b in targets:
            resolved[b].add(a)
    for m in data['methods']:
        m['related'] = sorted(resolved[m['id']])

    # 手法→書籍は参照（ref）で持つ。表示に必要な書誌は、ここで書籍レコードから展開する。
    # 正本では1冊＝1レコード（コピーが枝分かれして劣化しない）、
    # 生成物では手法に埋め込む（画面側が毎回引き直さなくて済む）。
    # note は「この手法にとってなぜこの本か」で、同じ本でも手法ごとに違うため参照側に置いてある。
    book_ix = {b['id']: b for b in data['books']}
    missing_books = []
    for m in data['methods']:
        out = []
        for ref in (m.get('books') or []):
            if not isinstance(ref, dict):
                continue
            bk = book_ix.get(ref.get('ref'))
            if not bk:
                missing_books.append((m['id'], ref.get('ref')))
                continue
            entry = {k: v for k, v in bk.items()
                     if k in ('title', 'author', 'publisher', 'year', 'level', 'essential')
                     and v not in (None, '')}
            if ref.get('note'):
                entry['note'] = ref['note']
            out.append(entry)
        m['books'] = out
    # 表示は main() に任せる。load_data はテストから何度も呼ばれるため、
    # ここで print すると同じ警告が繰り返し出て、本当の問題が埋もれる。
    data['_gaps'] = {'books': missing_books, 'related': missing_related}
    for i in data['institutions']:
        for k, v in INSTITUTION_DEFAULTS.items():
            i.setdefault(k, v() if callable(v) else v)
    return data, patch


def main():
    data, patch = load_data()
    gaps = data.pop('_gaps', {})

    concepts = apply_concepts(data, patch)
    remap_people_disciplines(data)
    disc_lineage_n = inject_discipline_lineage(data, patch)

    disc_ids = {d['id'] for d in data['disciplines']}
    data['facilitation_inflows'] = [
        e for e in patch['facilitation_inflows'] if e.get('from_id') in disc_ids]
    data['roadmap_books'] = {
        k: v for k, v in patch['roadmap_books'].items() if k in disc_ids}
    data['facilitation_applications'] = patch['facilitation_applications']

    data.pop('_gaps', None)
    report, broken = validate(data)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    for mid, ref in gaps.get('books', [])[:5]:
        print(f"⚠ {mid} が参照している書籍「{ref}」が見つかりません")
    mr = gaps.get('related', [])
    if mr:
        import collections as _c
        top = _c.Counter(t for _, t in mr).most_common(5)
        print(f"未作成の手法への参照 {len(mr)} 本（{len(set(t for _, t in mr))} 種）"
              f" よく参照されている順: {top}")
        print("  → まだ書かれていない手法の一覧は pipeline/report_gaps.py で見られる。")
        print()
    print(report)
    print(f"concepts: {concepts['concepts']} | methods by tier "
          f"1/2/3 = {concepts['tier1']}/{concepts['tier2']}/{concepts['tier3']}")
    print(f"人が指定した分類: {concepts['pinned']} 件"
          + (f" | 存在しない概念を指しているもの: {concepts['pinned_unknown']}"
             if concepts['pinned_unknown'] else ""))
    print(f"discipline lineage edges: {disc_lineage_n}")
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB)")
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
