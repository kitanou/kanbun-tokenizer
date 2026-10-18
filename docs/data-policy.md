# データ方針

## 採用条件

各データソースについて、少なくとも次を記録する。

- dataset / work / edition ID
- 上流URL、取得日、版・コミットSHA
- データ自体のライセンスと、上流テキストの権利情報
- 必要な帰属表示、ShareAlike等の条件
- 原文ファイルのSHA-256
- 変換手順と派生データの対応関係
- 再配布可能か、学習利用可能か、商用利用可能か

## 初期候補

### Chinese Classical Corpus
https://github.com/gujilab/chinese-classical-corpus

公開リポジトリはデータをCC0として案内している。採用時は実際に使用するファイル、バージョン、LICENSE、各素材の来歴を確認し、`data/manifest.csv` に記録する。

### Chinese Text Project
https://ctext.org/zh

サイト上の閲覧可否を自動取得許可とみなさない。サイト規約・API契約・アクセス制限を確認し、禁止されているスクレイピングは行わない。権利とアクセス条件が確認できるデータだけを使用する。

### Fanya Hanwen Corpus
https://github.com/ShiraTheMogul/fanyahanwen-corpus

リポジトリはCC BY-SA 4.0を掲げる。帰属表示と継承条件を確認し、CC0データとは別のマニフェスト区分で扱う。ライセンスの互換性を確認するまで、混合した学習済み成果物を無条件に再配布しない。

## 保存方針

- 大規模な原文・外部コーパスはGitに含めない。
- Gitには取得手順、マニフェスト、ハッシュ、ライセンス確認記録のみを置く。
- サンプル文は出典・権利状態が明確なもの、または自作の短文に限定。
- 不明なライセンスは「未確認」とし、採用・配布前に解決する。

## マニフェスト検証と分割

```bash
python -m kanbun_tokenizer.manifest validate data/manifest.csv --root <corpus-dir>
python -m kanbun_tokenizer.manifest split data/manifest.csv --root <corpus-dir> --output-dir artifacts/splits
```

- 必須項目欠落、SHA-256形式不正、権利が `unknown`/未確認、`training_allowed` が `yes` でない行、重複（work_id・SHA-256）は検証エラーとなり、分割は実行されない。
- 分割は `seed:work_id` のハッシュによる作品単位の決定的割当（既定 80/10/10）。作品の追加で既存作品の割当は変わらない。結果は `splits.json` に記録される。

## 調査記録（2026-10-18）

### gujilab/chinese-classical-corpus（commit 09a6873）
- `LICENSE`: 派生データ（`output/*.json`, `corpus.jsonl`）はCC0、コードはMIT。GitHub APIのライセンス判定は `NOASSERTION`。
- README上、多くの作品が「繁→简」変換済みの簡体字で、一部は ctext.org・wikisource・chtxt・NiuTrans 由来。本プロジェクトは繁体字を前提とし、繁簡の一律統合を避けるため、そのままでは主コーパスに不適。ctext.org由来行はアクセス条件の確認が済むまで除外する。
- 利用するなら、簡体字のままの PoC 用途に限り、作品ごとに上流（殆知阁・chinese-poetry）を確認する。

### 繁体字ソース候補（未確認）
- Kanripo（漢リポ, https://www.kanripo.org/ ）: GitHub `@kanripo` で公開。リポジトリ単位のライセンスと文字形の確認が必要。サイト表記にCC BY-SA 3.0/4.0の揺れがあるとの報告があり、ShareAlike区分で管理する。
- 中文維基文庫: 原典はパブリックドメインでも、wikiの編集内容はライセンス対象。原典ごとの権利と、帰属・継承条件の確認が必要。

## Kanripo PoC（2026-10-18）

論語・孟子・尚書・老子（`kanripo/KR1h0004`, `KR1h0001`, `KR1b0001`, `KR5c0057`）を `data/raw/kanripo/` に取得（Git管理外）。
`python -m kanbun_tokenizer.kanripo` で整形し、`data/manifest.csv` を生成する（`sha256` は整形後ファイルのもの、生データのcommitは `version`）。

- ライセンスは組織単位のCC BY-SA 4.0表記のみ。底本（CHANT／tls）の権利は未確認のため `upstream_rights`・`training_allowed` は `unknown`。通常の `validate` は失敗する。
- 内部PoCに限り `split --allow-unverified-rights` で警告扱いにできる。出力の `splits.json` は `release_eligible: false` となり、成果物の公開・配布には使えない。
- 4作品・約33万字のため、語彙16k以上のBPE評価には不十分。ByteLevelでは漢字1字が3バイトなので、小規模データではTPCが1を超える。

### 底本の権利調査（2026-10-18、Web検索による一次確認）

- **CHANT（漢達文庫, CUHK）**: 図書館ガイドによれば、データベース利用許諾により、CUHKの事前の書面承認なしの二次的著作物は認められず、引用時のクレジット表記も指定されている。契約全文は取得できなかった。→ 論語（`KR1h0004`, 底本CHANT）は `upstream_rights` に制限を記録し `training_allowed=no` とする。CUHK（Research Centre for Chinese Ancient Texts）の書面許諾を得るまで学習・配布に使わない。
- **tls（Thesaurus Linguae Sericae）**: 利用条件を見つけられなかった。孟子・尚書・老子は `unknown` のまま。TLS管理者（プロジェクトページ）またはKanripoへの問い合わせが必要。
- **Kanripo側**: 組織説明の「CC BY SA 4.0」以外に、リポジトリ別の権利表示や底本条件の記載は見つからなかった。CC BY-SAの表示が底本側の制限を上書きするとは扱わない。

結論: 現時点でマニフェスト検証を通る行はない。PoCは `--allow-unverified-rights --exclude KR1h0004` で、CHANT由来を除いた3作品だけを使う。
