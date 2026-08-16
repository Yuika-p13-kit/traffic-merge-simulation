# Traffic Merge Simulation

Python と Eclipse SUMO を使った車線合流（merge）シミュレーションの実験環境です。

## 概要

- 交通流の合流挙動を再現する
- Python から SUMO を起動して実験を実行する
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

SUMO のインストールと `SUMO_HOME` の設定が必要です。実行環境では以下のように設定してください。

```bash
export SUMO_HOME="/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO"
export PATH="$SUMO_HOME/bin:$PATH"
```

## 最小無制御合流モデル

現在の最小モデルは、主線 1 車線・従線 1 車線・合流後 1 車線の単純な構成です。

- 主線: 1000 veh/h
- 従線: 400 veh/h
- 車種: 1 種類
- 信号: なし
- Ramp Metering: なし

## 実行方法

### 1. GUI で動作確認

```bash
sumo-gui -c sumo/config/minimal_merge.sumocfg
```

### 2. Python から CLI 実行

```bash
uv run python main.py
```

この実行では SUMO を外部プロセスとして起動し、車両発生・走行・終了までを自動実行します。
結果は `experiments/minimal_merge_results.csv` に出力されます。

### 3. 生成されるファイル

- ネットワーク定義: `sumo/network/minimal_merge.net.xml`
- ノード定義: `sumo/network/minimal_merge.nod.xml`
- エッジ定義: `sumo/network/minimal_merge.edg.xml`
- ルート定義: `sumo/routes/minimal_merge.rou.xml`
- 設定ファイル: `sumo/config/minimal_merge.sumocfg`

## ディレクトリ構成

```text
traffic-merge-simulation/
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── traffic_merge_sim/
├── sumo/
│   ├── config/
│   ├── network/
│   └── routes/
├── experiments/
├── tests/
└── main.py
```

