# Highway merge v3 — Step 5: 完全版TTSによる評価

Step 4で最良だった改善2（並走区間全体を検知し、`main_merge_1`へ23.5 m/sを最大7秒助言）を固定し、無制御と同一seedで比較する。速度助言を再調整するStepではない。

評価対象は、3,950 veh/h・主線:ランプ=1:2・seed 7/42/99/123/2026である。道路上の滞在時間に、SUMOのpending vehicleとして観測される道路外の挿入待ち時間を加えた完全版TTSを主指標とする。主線・ランプ別TTS、未完了車両、処理量、および95% Student-t信頼区間を出力する。

```bash
uv run python experiments/highway_merge_v3/step05_evaluation/run.py
```

結果は `results/` にCSVとmetadataを保存する。判定は、完全版TTSの同一seed差の95%信頼区間と、安全性（衝突・テレポート0）を併せて行う。
