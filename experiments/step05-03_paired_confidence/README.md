# Step 5-3: 同一seed差と95%信頼区間

## 目的

Step 5-2の戦略別絶対値グラフに加え、同じ需要条件・同じseedの無制御と協調制御を一対一で比較する。平均差とseed間変動を分離し、小幅な平均改善と一貫した変化を区別する。

Step 5-2のシミュレーションは再実行せず、正式raw CSVを入力にする。

## 差と信頼区間

```text
paired_delta = cooperative_limited - uncontrolled
95% CI = mean(paired_delta) ± t(0.975, n-1) × sample_sd / sqrt(n)
```

TTS、未到着台数は負の差が改善、処理量は正の差が改善を表す。95%信頼区間が0をまたぐ場合は `uncertain` とする。

## 対象指標

- 完全版TTS
- ネットワーク内TTS
- 挿入待ちTTS
- 未到着台数
- 処理量（veh/h）

## 実行

```bash
uv run python experiments/step05-03_paired_confidence/run.py
```

別のStep 5-2 raw CSVを指定する場合:

```bash
uv run python experiments/step05-03_paired_confidence/run.py \
  --input-csv path/to/complete_tts_raw.csv \
  --output-dir path/to/results
```

## 成果物

- `results/paired_differences.csv`: 条件・seed・指標ごとの無制御値、協調値、差
- `results/paired_confidence_summary.csv`: 平均差、標準偏差、標準誤差、95%信頼区間、判定
- `results/figures/*.svg`: seed別点、平均、95%信頼区間を重ねた図
- `results/metadata.json`: 入力CSV、差と信頼区間の定義

図の色は、緑が改善、赤が悪化、灰色が95%信頼区間に0を含む不確定を表す。指標によって改善方向が異なるため、CSVの `lower_is_better` と `interpretation` を併記する。

正式結果とStep 5の完了判定は `RESULTS.md` を参照する。
