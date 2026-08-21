# Highway merge v3 — Step 1: 無制御ベースライン

`highway_merge_v3`（合流区間3車線、下流2車線）の無制御需要範囲を較正する。旧 `minimal_merge` および `highway_merge_v2` の結果は使用しない。

```bash
uv run python experiments/highway_merge_v3/step01_baseline/run.py
```

既定では主線 600 / 1,200 / 1,800 veh/h、ランプ 200 / 600 / 1,000 veh/h、各3 seedを実行する。需要は120秒間投入し、その後180秒のクリアランスを設ける。

各条件で次を記録する。

- クリアランス終了時の未完了車両
- SUMOの衝突・テレポート
- ピーク停止車両数、平均待ち時間、スループット

この結果で、Step 2の固定主線需要とランプ需要の広域探索範囲を定める。
