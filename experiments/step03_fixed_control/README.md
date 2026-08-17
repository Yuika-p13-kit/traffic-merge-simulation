# Step 3: 固定比率合流制御の比較

無制御、1:1、2:1、3:1、5:1などの固定合流戦略を、Step 2 と同じ条件・指標で比較する。

## 初期対象

- Step 2 で確認した `free_flow`、`queue`、`breakdown` の代表条件
- 特に `main=200 veh/h`、`side=818〜820 veh/h` の境界付近
- seed: 1〜5
- 需要投入: 1,800秒
- クリアランス: 600秒

## 実行方法

```bash
uv run python experiments/step03_fixed_control/run.py
```

短い動作確認の例:

```bash
uv run python experiments/step03_fixed_control/run.py \
  --main-rates 200 --side-rates 819 --strategies uncontrolled,1:1 \
  --duration 300 --clearance-time 120 --seeds 1
```

`1:1` や `5:1` は車線数や需要比ではなく、合流後へ実際に進入した「主線車両数 : 従線車両数」を表す。片側に車両がいない場合は、存在する側を通して道路容量を遊休させない。通行権を切り替える際は、競合する流入を同時に開放しないよう1シミュレーションステップの全赤を挟む。

生データ、seed間の集約結果、metadataは `results/` に保存する。無制御と固定制御で共通の結果列を使い、Total Travel Time、待ち時間、最大待ち行列、スループットを比較できる。

## 終了条件

- 無制御と各固定比率を同一条件で再現できる
- 通過比率が需要比とは独立して動作する
- 複数seedの生データ、集約結果、条件が保存される
- テストが成功する
