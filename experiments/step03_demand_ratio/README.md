# Step 3: 無制御合流の需要比比較

信号などの制御を追加せず、Step 2と同じ高速道路型の優先合流で、主線とサブの需要配分が結果に与える影響を確認する。

`1:4` は「主線需要1 : サブ需要4」を表す。合流順序や通過台数を強制する比率ではない。

## 実験条件

- 総需要: 800 / 1,000 / 1,200 veh/h
- 主線需要 : サブ需要: 1:1 / 1:2 / 1:3 / 1:4 / 1:5
- seed: 1〜5
- 需要投入: 1,800秒
- クリアランス: 600秒
- 合流制御: なし

総需要を固定したまま需要比だけを変えることで、交通量の総量と主線・サブへの配分の影響を分離する。

## 実行方法

```bash
uv run python experiments/step03_demand_ratio/run.py
```

短い動作確認の例:

```bash
uv run python experiments/step03_demand_ratio/run.py \
  --total-rates 1000 --demand-ratios 1:3,1:4,1:5 \
  --duration 300 --clearance-time 120 --seeds 1
```

生データ、seed間の集約結果、metadataは `results/` に保存する。

正式結果と解釈は `RESULTS.md`、公開記事向け原稿は `docs/qiita_step03.md` を参照する。
