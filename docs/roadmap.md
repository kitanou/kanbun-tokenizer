# Roadmap

## M0 — Project foundation
- [ ] README、技術設計、データ方針を確定
- [ ] Python package / CLI / tests / CI
- [ ] データマニフェストのスキーマを定義
- [ ] サンプルでtrain/evaluateが実行できること

## M1 — Reproducible baseline
- [ ] 利用条件が明確な初期コーパスを選定
- [ ] 文献ID・重複除去・作品単位split
- [x] 16k / 32k / 64k BPEの学習（`kanbun_tokenizer.baseline`）
- [x] 文字単位対照群と共通評価器
- [ ] 実験環境・設定・データ版をレポートに記録

## M2 — Classical Chinese linguistic analysis
- [ ] 機能語リストと出典を文書化
- [ ] 否定・判断・疑問・反語等の評価セットを作成
- [ ] 頻出熟語と句法候補の分割分析
- [ ] 繁体字・異体字・句読点の影響を評価

## M3 — Specialized tokenizer
- [ ] 語彙候補の注入／スコア補正方式を設計
- [ ] 標準BPEに対するアブレーション実験
- [ ] 未見作品での性能を検証
- [ ] 可逆性・未知文字テストを拡充

## M4 — Release
- [ ] データとモデル成果物のライセンスレビュー
- [ ] APIと互換性ポリシー
- [ ] バージョン付きモデルカード・評価レポート
- [ ] 初回リリース
