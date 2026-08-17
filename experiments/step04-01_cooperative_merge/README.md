# Step 4-1: 協調的な自然合流（初期方式）

Step 3でbreakdownした総需要1,000 veh/h・需要比1:2〜1:3を対象に、主線を停止させずに合流ギャップを作る協調制御を試す。

## 制御方法

1. サブ車両が合流点の80m以内で2秒以上待ったことを検知する
2. 主線の合流点40〜180m手前にいる最も近い車両を1台選ぶ
3. 選んだ車両へ15 m/sの速度助言を与え、前方にサブ車両が入れるギャップを作る
4. 条件が解消したらSUMO本来の速度制御へ戻す

信号・停止線・主線の完全停止は使用しない。制御値は初期仮説であり、結果を見て感度分析する。

## 初期条件

- 総需要: 1,000 veh/h
- 需要比（主線:サブ）: 1:2 / 1:3
- 比較: uncontrolled / cooperative
- seed: 1〜5
- 需要投入: 1,800秒
- クリアランス: 600秒

## 実行方法

```bash
uv run python experiments/step04-01_cooperative_merge/run.py
```

短い動作確認:

```bash
uv run python experiments/step04-01_cooperative_merge/run.py \
  --total-rates 1000 --demand-ratios 1:2 \
  --strategies uncontrolled,cooperative \
  --duration 300 --clearance-time 120 --seeds 1
```

結果は `results/cooperative_raw.csv`、`results/cooperative_summary.csv`、`results/metadata.json` に保存する。

正式結果と失敗要因の分析は `RESULTS.md` を参照する。この初期方式は介入過多で無制御より性能が悪化したため、改善版は別のStep 4-2として扱う。
