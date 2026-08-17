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

このエントリポイントは、現時点の最小無制御ケースを手早く確認するための convenience 実行です。
将来の実験拡張で `main.py` の既定挙動が変わる可能性があるため、公開用のベースライン再現には次のステップ別スクリプトを使ってください。

### 3. 公開用の無制御ベースラインスイープ

```bash
uv run python experiments/step01_baseline/run.py \
  --main-rates 20,40,60 \
  --side-rates 10,20,30 \
  --duration 1800 \
  --seed 42
```

このスクリプトは結果を `experiments/step01_baseline/results/baseline.csv`、条件を同じ場所の `metadata.json` に保存します。
SUMO の中間生成物は `sumo/output/generated/` に出力され、公開用成果物とは分離されます。
公開用の比較実験や記事の再現にそのまま使える、安定したベースライン再現コマンドです。

容量限界を確認する広域スイープは `uv run python experiments/step02_throughput/run.py` で実行します。

無制御と固定通過比率（主線車両数 : 従線車両数）を比較する Step 3 は次で実行します。

```bash
uv run python experiments/step03_fixed_control/run.py
```

### 4. 生成されるファイル

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
│   ├── common/
│   ├── step01_baseline/
│   ├── step02_throughput/
│   └── step03_fixed_control/
├── tests/
└── main.py
```
