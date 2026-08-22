# Highway merge v3 — Step 6: 固定間隔Ramp Metering

Step 5の完全版TTS評価基盤を使い、主線を制御せずランプ投入だけを平準化する固定間隔Ramp Meteringを検証する。

- ネットワーク: `highway_merge_v3`
- 需要: 3,950 veh/h（主線1,317、ランプ2,633）、1,800秒投入＋600秒クリアランス
- seed: 7 / 42 / 99 / 123 / 2026
- 比較: 無制御、Step 4の限定協調合流、ランプ放流1.0 / 1.25 / 1.5秒
- 主指標: 完全版TTS（道路内滞在＋道路外の挿入待ち）

```bash
uv run python experiments/highway_merge_v3/step06_ramp_metering/run.py
```

実行時に代表ケース（固定1秒・最初のseed）のFCD XMLだけを `sumo/output/generated/trajectories/v3-step06/` へ保存する。0〜120秒を、`frame-step=1`、`fps=10`でGIF化し、`sumo/output/generated/visualization/v3-step06-ramp-fixed-1s.gif` に保存する。FCDとGIFはいずれもGit管理外の再生成物である。

`results/` にはケース別CSV、戦略別平均、無制御との差の同一seed 95%信頼区間、再現条件を保存する。

非整数の放流間隔を比較する場合は、`--step-length 0.25` のように、最小放流間隔を表現できる時間刻みを指定する。Step 6-2ではこの条件で再評価し、固定間隔方式を終了した。
