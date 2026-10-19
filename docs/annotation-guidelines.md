# 機能語・句法評価セット: スキーマと注釈ガイドライン

issue 04 の評価セットの設計。**この文書は設計であり、注釈済みデータはまだ存在しない。** 候補例の抽出は `kanbun_tokenizer.candidates`、検証は同モジュールの `--validate`。

## 1. 目的と原則

- 目的: 分割が漢文の語彙・機能語・句法パターンに沿うかを、**人手で注釈した事例**に対して測る。
- 圧縮率（TPC）から句法上の主張を導かない。分割が「正しい」かどうかは、注釈者が根拠付きで宣言した期待（§4）に対してのみ評価する。
- 期待が定まらない事例（多義・用法が割れる事例）は `no_expectation` とし、評価の主指標から除く。無理に一つの解釈へ寄せない。
- 注釈者が一人の間は、注釈者間一致度は主張できない（§7）。

## 2. 対象現象（初期セット）

| phenomenon | pattern | 備考 |
|---|---|---|
| negation | 不・未・無・非 | 「無」は存在動詞／禁止（毋・勿に通じる）／否定副詞の別がある |
| final_particle | 也・矣・焉 | 「焉」は兼語（於此）的用法、「也」は主題提示用法など文中用法がある |
| question | 乎・耶・邪・歟・豈 | 「乎」は前置詞（於）的用法、「豈」は反語を作る |
| pattern | 不亦…乎、何…之有、豈…哉／乎／耶、如…何、無乃…乎 | 離れた要素を含む。ここでは表層の一致のみ。他の句法は注釈者の提案で追加（根拠付き） |

## 3. レコード（JSONL、1行1事例）

抽出スクリプトが埋めるフィールド:

| フィールド | 内容 |
|---|---|
| `id` | 出典・位置・パターンから決まる12桁のSHA-1。再抽出しても変わらない |
| `phenomenon`, `pattern` | 上表 |
| `text` | 文（NFC）。`。？！` で区切り、既定で8〜60文字 |
| `span` | `text` 上の目標 `[start, end)`（Unicodeコードポイント。`text[start:end] == matched`） |
| `matched` | 目標の文字列。パターンでは「不亦…乎」全体 |
| `context` | `clause_final`（直後が読点・句点・引用閉じ・文末）, `sentence_initial` |
| `provenance` | `dataset_id`, `work_id`, `line`（処理済みテキストの行）, `sentence_offset`, `page_title`, `oldid`（Wikisourceの版）, `source_sha256`, `data_license` |
| `corpus_split` | 出典作品のcorpus split（train / validation / test / unknown） |
| `status` | `candidate` → `annotated` → `audited`、不採用は `rejected` |
| `annotation` | 候補段階では `null` |

注釈者が追記する `annotation`:

| フィールド | 内容 |
|---|---|
| `function` | 現象ごとの許容値（下表）。多義の区別を表す |
| `is_target_use` | その現象の典型用法か。`false` なら反例 |
| `expectation` | `separable`（目標が隣接語と独立の単位として復元できることが望ましい）／`unit`（複数文字がまとまることが望ましい）／`no_expectation` |
| `rationale` | 判断理由（1〜3文） |
| `reference` | `separable`・`unit` のとき必須。文法書・辞書・注釈などの根拠（書名・版・頁／条）。**確認できない文献は書かない** |
| `ambiguity` | `low`／`medium`／`high` |
| `annotator`, `annotated_at` | 注釈者と日付 |
| `audit` | `{auditor, agrees, notes}`（§7）。`status: audited` で必須 |

`function` の許容値:

| phenomenon | 値 |
|---|---|
| negation | `adverbial_negation`, `existential_wu`, `prohibitive`, `copular_negation`, `other` |
| final_particle | `final_particle`, `non_final_use`, `pronoun_or_locative`, `other` |
| question | `interrogative_particle`, `rhetorical`, `preposition_or_other`, `other` |
| pattern | `pattern_instance`, `not_a_pattern`, `other` |

## 4. 注釈規則

1. **文脈で判断する**。文字だけでなく、前後の語と文全体から用法を決める。決めきれなければ `ambiguity: high`、`expectation: no_expectation`。
2. **反例を必ず含める**。各現象について、典型用法でない事例（`is_target_use: false`）を全体の25%以上にする。例: 「乎」が疑問でなく前置詞「在乎〜」、「無」が存在動詞、「也」が文中の主題提示。抽出スクリプトは節末／節中を交互に抽出して、反例が混ざりやすくしている。
3. **`expectation` の意味**: `separable` は「目標を含む最小のまとまりが、隣の文字を巻き込まない」ことを求める主張で、分割がそうなっていなくても誤りとは限らない（語彙化した連語もある）。このため `separable`・`unit` は根拠を要し、評価では分割の「正誤」ではなく**期待との一致率**として報告する。
4. **パターン（不亦…乎 等）**: 目標は構成要素（「不亦」「乎」）の位置を `rationale` に書く。間に入る語は自由なので、全体が1トークンになることは期待しない。期待を置くなら、枠の各要素（例: 「不亦」と「乎」）が別のトークンに吸収されていないか、という限定した形にする。
5. **異体字・字形**: 原文の字形を変えない。注釈で別字形に言及する場合は `rationale` に書く。
6. **編集記号**: 抽出テキストは校訂記号（`（…）` 削除、`〔…〕` 括弧除去）を処理済み。目標の周辺に校訂による補い字が含まれる事例は `rejected` にするか、`rationale` に明記する。
7. **本文性の確認**: 注釈者は、`text` が古典の本文であること（注・解説・現代語でないこと）を確認し、そうでなければ `rejected`。（抽出テキストに注釈由来の文が混入している可能性がある。）

## 5. 出典と権利

- 全事例に `provenance` が必須。`oldid` と `data/wikisource-fetch-log.csv` で版が追える。
- 例文は CC BY-SA 4.0 区分（zh.wikisource の編集内容）の作品から取るため、**評価セットも ShareAlike 区分で管理**する。帰属表示は作品名・ページ名・oldid。学習済み成果物への影響は未審査。
- 公開リリース前に、各作品の権利状態を `docs/data-policy.md` の基準で再確認する。

## 6. 学習データとの分離

- 評価セットは **validation / test の作品だけ** から作ることを推奨する（`--only-split validation test`）。
- train 作品から取る場合は、その文を当該評価のための学習データから除外してトークナイザーを学習し直す。除外した文のIDを結果に記録する。
- 抽出スクリプトは `corpus_split` を付けるので、結果レポートで split 別に集計できる。

## 7. 監査と品質基準

- 第二パス監査: 全事例の20%以上（`ambiguity` が `medium`／`high` の事例は全数）を、別の人が独立に見直し、`annotation.audit` に `auditor`・`agrees`・`notes` を記録する。
- 監査者が別人でない場合（現状は注釈者が1人）、レポートに「注釈者間一致度は未測定」と明記する。同一人物による再見直しは監査に数えない。
- 不一致は協議して、結論と理由を `notes` に残す。解消しない事例は `no_expectation` にする。
- 受入基準（issue 04 に対応）: 全事例に出典がある／注釈規則が文書化されている／第二パス監査が完了している／句法上の主張を圧縮率だけから推論していない。

## 8. 作業手順

```bash
python -m kanbun_tokenizer.candidates \
  --manifest data/manifest-wikisource.csv --root data/processed/wikisource \
  --splits artifacts/splits-wikisource/splits.json --only-split validation test \
  --output artifacts/eval-candidates/candidates.jsonl
# 注釈後
python -m kanbun_tokenizer.candidates --validate data/eval/functionwords/examples.jsonl
```

- 候補は現象×パターン×作品で層化し、ハッシュ順で決定的に抽出する（`--seed`、`--per-pattern-per-work`、`--per-pattern`）。
- 抽出は文字列一致のみで、用法の判定はしない。候補件数は偏りがあるので、少ないパターンは作品を増やして補う。
- 処理済みテキストと `*.sources.tsv`（行→ページ・oldid）は `python -m kanbun_tokenizer.wikitext` が生成する。

## 9. パイロット下書き（10件）

`data/eval/functionwords/drafts-pilot10.jsonl`: 論語・呂氏春秋（held-out）から8パターンを選び、`draft_annotation` に注釈案を付けた10件（うち4件が反例）。

- **これは注釈ではない**。`status` は `candidate`、`annotation` は `null` のまま。案は Claude が作ったもので、文法書・辞書などの根拠は確認していない。
- `proposed_expectation` はすべて `no_expectation`。`separable`／`unit` には根拠（`reference`）が必須で、その確認を人間が行うまで置けないため。
- 人間は `draft_annotation` を見直し、確定したものを `annotation`（`annotator`・`annotated_at`・必要なら `reference` を追加）に移して `status: annotated` にする。
