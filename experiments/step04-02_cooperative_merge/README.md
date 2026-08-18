# Step 4-2: 限定介入型の協調合流

Step 4-1の連続介入を改善し、主線車両への速度助言を必要な競合時だけに限定する。

## Step 4-1からの変更

- 速度助言: 15.0 → 22.5 m/s
- 主線車両の到着予測時間が2〜8秒の場合だけ介入
- 介入中は対象車両を切り替えない
- 介入開始時に先頭の待機サブ車両を記録し、その車両の合流完了を検知したら介入を終了
- 最大8秒で強制終了
- 終了後8秒間は再介入しない
- 成功終了・タイムアウト回数を記録

信号、停止線、主線の完全停止は使用しない。

## 実行方法

```bash
uv run python experiments/step04-02_cooperative_merge/run.py
```

短い動作確認:

```bash
uv run python experiments/step04-02_cooperative_merge/run.py \
  --total-rates 1000 --demand-ratios 1:2 \
  --strategies uncontrolled,cooperative_limited \
  --duration 300 --clearance-time 120 --seeds 1
```

初期方式のコード・結果は `experiments/step04-01_cooperative_merge/` に残し、試行間の差を追跡できるようにする。

正式結果と考察は `RESULTS.md`、試行錯誤を含む公開記事向け原稿は `docs/qiita_step04_02.md` を参照する。
