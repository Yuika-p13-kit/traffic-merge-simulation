# Traffic Merge Simulation

Python と Eclipse SUMO を使った車線合流（merge）シミュレーションの実験環境です。

## 概要

- 交通流の合流挙動を再現する
- Python から SUMO を制御する
- 実験設定を `experiments/` 配下で管理する
- シミュレーション用のネットワークとルートを `sumo/` 配下に配置する

## プロジェクト文書

- 詳細なプロジェクト概要: `PROJECT_OVERVIEW.md`

## 前提条件

- Python 3.13+
- uv
- Eclipse SUMO

## セットアップ

```bash
uv sync
```

SUMO のインストールと `SUMO_HOME` の設定が必要です。

## ディレクトリ構成

```text
traffic-merge-simulation/
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── traffic_merge_sim/
├── sumo/
│   ├── network/
│   └── routes/
├── experiments/
├── tests/
└── main.py
```

