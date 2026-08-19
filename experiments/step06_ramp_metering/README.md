# Step 6: サブ側固定間隔Ramp Metering

Step 5で完成した挿入待ち込みTotal Time Spent（完全版TTS）と同一seed差の評価基盤を使い、サブ側だけを制御する固定間隔Ramp Meteringがネットワーク全体の損失を減らすか検証する。

比較対象は無制御、限定協調合流（Step 4-2）、固定放流間隔4 / 6 / 8秒。総需要800 / 1,000 / 1,200 veh/h、主線:サブ比1:1〜1:5、seed 1〜5を共通条件とする。サブ車両を `side_in` の330 m地点で保持し、各間隔で先頭1台だけを解放する。主線は停止させない。

```bash
uv run python experiments/step06_ramp_metering/run.py
```

短い動作確認例:

```bash
uv run python experiments/step06_ramp_metering/run.py \
  --total-rates 1000 --demand-ratios 1:3 \
  --strategies uncontrolled,ramp_fixed_6s \
  --duration 120 --clearance-time 60 --seeds 1,2
```

`results/` にraw CSV、同一seed差、95%信頼区間、SVG、metadataを出力する。差は `strategy - uncontrolled` で、TTSでは負が改善を表す。
