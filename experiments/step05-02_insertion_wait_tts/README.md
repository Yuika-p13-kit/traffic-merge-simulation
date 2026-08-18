# Step 5-2: 挿入待ち時間を含むTTS

## 目的

Step 5-1のTTSはネットワーク内にいる全車両を含むが、予定出発時刻を過ぎても流入エッジへ挿入できない車両を含まない。Step 5-2ではSUMOのpending vehicleを各ステップで観測し、道路外の挿入待ち時間をTTSへ追加する。

## TTSの定義

```text
network_time_spent_s = Σ（ネットワーク内車両数 × ステップ長）
insertion_wait_time_s = Σ（挿入待ち車両数 × ステップ長）
total_time_spent_s = network_time_spent_s + insertion_wait_time_s
```

主線・サブ別にも同じ3値を出力する。挿入待ち車両は、SUMOの `simulation.getPendingVehicles()` が返す、予定出発時刻を過ぎても道路へ入れない車両である。

## 整合性検証

各ランで次を記録する。

- `accounted_loaded_veh`: TraCIのloaded IDを累積した台数
- `loaded_vehicles`: SUMO summaryの最終loaded台数
- `loaded_reconciliation_error_veh`: 上記2値の差

標準実験では `loaded_reconciliation_error_veh == 0` を期待する。これにより、TTSの対象母集団がSUMOのロード車両と一致するか確認できる。

## 実行

```bash
uv run python experiments/step05-02_insertion_wait_tts/run.py
```

短い動作確認例:

```bash
uv run python experiments/step05-02_insertion_wait_tts/run.py \
  --total-rates 1200 --demand-ratios 1:5 \
  --strategies uncontrolled,cooperative_limited \
  --duration 120 --clearance-time 60 --seeds 1
```

## 成果物

- `results/complete_tts_raw.csv`: seedごとの完全版TTSと既存指標
- `results/complete_tts_summary.csv`: 条件・戦略ごとの平均
- `results/figures/*.svg`: 完全版TTS、ネットワーク内TTS、挿入待ちTTSなど
- `results/metadata.json`: 条件とTTS定義

Step 5-1の正式結果は変更しない。Step 5-2の正式結果と考察は `RESULTS.md` を参照する。
