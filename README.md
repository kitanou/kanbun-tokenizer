# 漢文tokenizer

古典漢文に特化したトークナイザーを研究・開発する独立プロジェクトです。漢文の語彙・機能語・句法を反映しつつ、復元性、速度、汎化性能を測定します。

> **研究上の原則:** トークン化は句法解析そのものではありません。v0.x では、可逆な文字列トークナイズを土台に、漢文語彙・機能語・句法候補の分析を重ね、効果を実験で検証します。

## 目標

- 古典漢文の語彙・機能語・句法に配慮した語彙を構築する
- 標準BPEをベースラインとして、漢文特化方式と公平に比較する
- Unicode文字列の復元性を保ち、未知文字・異体字の扱いを明示する
- 学習データの出典・ライセンス・変換履歴を記録する
- Apple Silicon Mac で再現可能な実験を提供する

## 非目標（初期段階）

- LLM本体の事前学習・ファインチューニング
- 漢文の意味をトークナイザーだけで完全に理解すること
- 原文を無断で大量収集するスクレイピング
- 異体字を原文記録なしに一律統合すること

## 開発環境

- macOS / Apple Silicon（開発基準機：M5 Max、ユニファイドメモリ64GB）
- Python 3.12+
- Hugging Face `tokenizers`（Rust実装）
- pytest

## クイックスタート

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dev]'
pytest
```

サンプルテキストでベースラインを学習します。

```bash
python -m kanbun_tokenizer.train \
  --input data/sample/corpus.txt \
  --output artifacts/bpe-16k/tokenizer.json \
  --vocab-size 16000
```

トークン数と復元性を評価します。

```bash
python -m kanbun_tokenizer.evaluate \
  --tokenizer artifacts/bpe-16k/tokenizer.json \
  --input data/sample/eval.txt \
  --output artifacts/bpe-16k/evaluation.json
```

初期サンプルは動作確認用であり、性能評価の根拠には使用しません。

## データ方針

第一候補として [Chinese Classical Corpus](https://github.com/gujilab/chinese-classical-corpus) を調査します。公開リポジトリはデータをCC0として案内していますが、採用時には対象ファイル・上流出典・版・ライセンス表記を改めて記録します。データセット全体のライセンス表示だけで、全ての上流素材の権利が自動的に解決するとはみなしません。

- [CTP / Chinese Text Project](https://ctext.org/zh): サイトの自動取得制限とAPI条件を確認し、許可された取得方法のみを使用する
- [Fanya Hanwen Corpus](https://github.com/ShiraTheMogul/fanyahanwen-corpus): CC BY-SA 4.0とされるため、帰属表示・継承条件を確認し、CC0データと分離管理する
- データをリポジトリにコミットしない。取得手順、出典、チェックサム、ライセンス台帳をコミットする

詳細は [`docs/data-policy.md`](docs/data-policy.md)。

## 初期設計

- ベースライン: BPE、語彙サイズ16k / 32k / 64k
- 対照群: 文字単位フォールバック、標準BPE、漢文語彙を考慮した候補方式
- 正規化: 初期設定ではUnicode NFCのみ。繁簡変換・異体字統合は別実験として扱う
- 評価: tokens/character、encode速度、decode速度、完全復元率、未見作品での性能、機能語・句法候補の分割傾向
- 分割: 作品単位で train / validation / test を分け、同一作品の漏洩を避ける

## リポジトリ構成

```text
configs/                 実験設定
data/sample/             動作確認用の短いサンプルのみ
docs/                    技術設計・データ方針・ロードマップ
issues/                  GitHub Issueへ登録する初期Issue本文
src/kanbun_tokenizer/    学習・評価コード
tests/                   自動テスト
artifacts/               生成物（Git管理対象外）
```

## ロードマップ

- **M0 — 基盤:** データ台帳、正規化方針、CLI、CI
- **M1 — ベースライン:** BPE 16k/32k/64k、再現可能な評価レポート
- **M2 — 漢文語彙分析:** 機能語・頻出熟語・句法候補の分布分析
- **M3 — 漢文特化方式:** 語彙制約や候補スコアリングを追加し、対照実験
- **M4 — 公開評価:** 未見作品での評価、モデル連携用成果物、リリース

## ライセンス

コードは初期案として MIT License を採用します。データと学習済み成果物はコードとは別のライセンス台帳で管理します。`LICENSE` を確定する前に、公開者の意図とプロジェクト方針を確認してください。
