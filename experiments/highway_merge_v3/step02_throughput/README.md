# Highway merge v3 — Step 2: 無制御時の容量境界

v3 Step 1で全seedの流出完了・衝突なし・テレポートなし・停止待ち行列なしを確認した主線1,800 veh/hを固定し、ランプ需要を増やして容量境界を測定する。

```bash
uv run python experiments/highway_merge_v3/step02_throughput/run.py
```

既定の広域スイープはランプ0〜3,600 veh/hを400刻み、5 seed、需要投入1,800秒、クリアランス600秒で実行する。`breakdown` が現れたら、その直前・直後をより細かい刻みで再実行する。

- `recovered`: クリアランス終了までに全車両が到着した
- `breakdown`: クリアランス終了後も未完了車両が残った

車線変更中の短時間の停止だけでは `breakdown` と判定しない。seed間は多数決で集約し、同数なら安全側で `breakdown` とする。
