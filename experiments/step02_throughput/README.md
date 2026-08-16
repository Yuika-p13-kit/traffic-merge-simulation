# Step 2: 交通量・容量スイープ

主線・従線需要を広く変化させ、スループットと未完了車両数から容量限界と破綻領域を確認する。

```bash
uv run python experiments/step02_throughput/run.py
```

条件は `config.py`、公開結果と再現用metadataは `results/` に保存する。
