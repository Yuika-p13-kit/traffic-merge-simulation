# Highway merge v3 — Step 3: 無制御時の需要比比較

`highway_merge_v3` で総需要を固定し、主線:ランプ需要比だけを変えて無制御合流の回復・破綻と損失を比較する。旧 `minimal_merge` および `highway_merge_v2` の結果は使用しない。

Step 2の最初の多数決破綻点（総需要4,000 veh/h）の直前・直上を比べるため、既定では総需要3,950 / 4,000 veh/h、需要比1:1〜1:5、各5 seedを実行する。

```bash
PYTHONPATH=src uv run python experiments/highway_merge_v3/step03_demand_ratio/run.py
```

短い動作確認では、出力先も分ける。

```bash
PYTHONPATH=src uv run python experiments/highway_merge_v3/step03_demand_ratio/run.py \
  --total-rates 4000 --demand-ratios 1:1,1:3 --seeds 7 \
  --duration 120 --clearance-time 180 --output-dir /tmp/highway-v3-step03-smoke
```

`breakdown` は、クリアランス終了時に未完了車両が1台以上残る場合だけに付ける。車線変更などの短時間停止は単独では破綻としない。seed間は多数決で集約し、同数なら安全側の `breakdown` を採用する。

生データ、条件別集約、再現条件は `results/` に保存する。

正式結果、代表条件の選定、目標達成度は [`RESULTS.md`](RESULTS.md) を参照する。
