# Step 5-1: ネットワーク内TTSと流入別評価

## 目的

主線平均だけではなく、主線・サブ双方の負担と未到着車両の損失を同じ基準で比較できるようにする。Step 4-2 の制御条件は固定し、評価方法だけを拡張する。

## 追加する指標

- 主線・サブ別の平均待ち時間、総待ち時間、ピーク待ち行列
- 主線・サブ別の到着・未到着台数
- 未到着車両もシミュレーション終了まで加算する Total Time Spent (TTS)
- 介入開始後 30 秒以内に合流したユニークなサブ車両数
- 既存の状態分類、スループット、未到着台数

TTS は各シミュレーションステップでネットワーク内にいる全車両の滞在時間を積算する。tripinfo に記録されない未到着車両も評価に含む。ただし、出発予定時刻を過ぎてもネットワークへ挿入できていない車両の待ち時間は含まない。この制約は Step 5-2 で解消する。

## 実行

標準条件（3交通量 × 5需要比 × 2戦略 × 5 seed）は次で実行する。ディレクトリ名は初回実装時の再現コマンドとの互換性のため維持している。

```bash
uv run python experiments/step05_metrics_visualization/run.py
```

短い動作確認例:

```bash
uv run python experiments/step05_metrics_visualization/run.py \
  --total-rates 800 --demand-ratios 1:2 \
  --strategies uncontrolled,cooperative_limited \
  --duration 120 --clearance-time 60 --seeds 1
```

## 成果物

- `results/metrics_raw.csv`: seed ごとの全指標
- `results/metrics_summary.csv`: 需要条件・戦略ごとの平均
- `results/figures/*.svg`: TTS、流入別待ち時間、サブ待ち行列、処理量、介入後合流数
- `results/metadata.json`: 実験条件と生成ファイル一覧

SVG は Python 標準ライブラリだけで生成するため、可視化用の追加依存関係は不要。

正式結果と考察は `RESULTS.md` を参照する。
