# Highway merge v3 — Step 6-2: 時間刻みを揃えた固定間隔Metering再評価

Step 6の1.25秒・1.5秒比較はSUMOの既定1秒step-lengthで離散時刻へ丸められた。Step 6-2では、無制御・協調制御・固定Meteringのすべてを `step-length=0.25` で実行し、完全版TTSも0.25秒単位で積分する。

```bash
uv run python experiments/highway_merge_v3/step06_ramp_metering/run.py \
  --step-length 0.25 \
  --output-dir experiments/highway_merge_v3/step06_02_time_resolution/results \
  --fcd-output-dir sumo/output/generated/trajectories/v3-step06-02 \
  --gif-output sumo/output/generated/visualization/v3-step06-02-ramp-fixed-1s.gif
```

代表ケースだけFCDとGIFを生成する。比較条件はStep 6と同じで、無制御、限定協調合流、固定1.0 / 1.25 / 1.5秒、5 seedである。
