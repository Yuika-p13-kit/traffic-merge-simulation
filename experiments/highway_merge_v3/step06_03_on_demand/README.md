# Highway merge v3 — Step 6-3: オンデマンドRamp Metering

固定間隔方式を終了した後、主線の低速状態が持続したときだけ1.5秒間隔Meteringを作動させる方式を検証する。

- 作動: `main_merge_1` の平均速度が27 m/s以下で3秒継続
- 解除: 平均速度29 m/s以上が10秒継続、かつ30秒以上作動
- 時間刻み: 0.25秒
- 比較: 無制御、限定協調合流、固定1.5秒、オンデマンド1.5秒
- 評価: 完全版TTS、同一seed差・95%CI、安全性、作動回数・作動時間

```bash
uv run python experiments/highway_merge_v3/step06_03_on_demand/run.py
```

代表ケースだけFCDを保存し、0〜30秒を `frame-step=1`、`fps=10`でGIF化する。
