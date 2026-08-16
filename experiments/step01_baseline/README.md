# Step 1: 無制御ベースライン

最小合流ネットワークが自由流から減速・待ち行列へ遷移することを、低負荷レンジで確認する。

```bash
uv run python experiments/step01_baseline/run.py
```

条件は `config.py`、公開結果と再現用metadataは `results/` に保存する。
