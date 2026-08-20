# Highway merge v2 — Step 1: 無制御ベースライン

`highway_merge_v2` だけを対象に、低需要条件で自由流と流出完了を確認する。旧 `minimal_merge` の結果は使用しない。

```bash
uv run python experiments/highway_merge_v2/step01_baseline/run.py
```

主線200〜600 veh/h、ランプ100〜300 veh/hを3 seedで実行する。需要は120秒間、需要終了後180秒間を流出確認時間とする。
