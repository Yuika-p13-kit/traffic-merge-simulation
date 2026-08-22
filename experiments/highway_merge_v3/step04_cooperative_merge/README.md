# Highway merge v3 — Step 4: 限定的な協調合流

主線への限定的な速度助言が、信号・停止線・主線停止なしでランプ合流を支援できるか検証する。

```bash
PYTHONPATH=src uv run python experiments/highway_merge_v3/step04_cooperative_merge/run.py
```

高需要・ランプ偏重の代表条件では破綻回復に至らなかった。結果と後続Step 5/6への利用は [`RESULTS.md`](RESULTS.md) を参照する。
