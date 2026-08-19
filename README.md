# Traffic Merge Simulation

> **研究状態（2026-08-19）:** `minimal_merge` を用いたStep 1〜6-2の初期研究は、可視化により想定ネットワークとの不一致が判明したためクローズしました。既存結果はこの抽象ネットワークにのみ有効です。終了判断と再始動条件は [`docs/research_closure_2026-08-19.md`](docs/research_closure_2026-08-19.md) を参照してください。新しい研究は同じリポジトリ内に別ネットワークとして追加します。

Python と Eclipse SUMO を使った車線合流（merge）シミュレーションの実験環境です。

## 概要

- 交通流の合流挙動を再現する
- Python から SUMO を起動して実験を実行する
- 実験設定を `experiments/` 配下で管理する
- シミュレーション用のネットワークとルートを `sumo/` 配下に配置する

## プロジェクト文書

- 詳細なプロジェクト概要: `PROJECT_OVERVIEW.md`
- 初期研究の終了レポート: `docs/research_closure_2026-08-19.md`

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

## 高速道路型合流モデル（v2）

新しい研究系列は `highway_merge_v2` を使います。主線（上流2車線）、ランプ、600 m の並走合流区間、下流1車線を明示したネットワークです。旧 `minimal_merge` と結果・監視区間を共有しません。

- ネットワーク: `sumo/network/highway_merge_v2.net.xml`
- ネットワーク設定と監視区間: `src/traffic_merge_sim/network_config.py`
- 無制御ケースのPython入口: `traffic_merge_sim.highway_merge.run_highway_single_case`

Step 1〜3 はこのネットワークで需要範囲と合流長を再較正してから実施します。Step 4〜6 の制御実験は、その後に本系列専用として追加します。

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

### 合流状態の静止画可視化

SUMO-GUIを使わず、SUMO標準のFCD出力を基に指定時刻の状態をPNGとして保存できます。道路形状はネットワーク定義から読み込み、主線車両を青、従線車両を赤で表示します。

```bash
uv run python -m traffic_merge_sim.visualize \
  --main-rate 200 --side-rate 820 --duration 600 --seed 42 --time 300
```

高速道路型ネットワークを描画する場合は、`--network highway_merge_v2` を指定します。画像とFCDはネットワーク名ごとの出力先に分離されます。

既定では、FCD中間データとPNGを `sumo/output/generated/visualization/` に生成します。このディレクトリはGit管理対象外なので、同じコマンドでいつでも再生成できます。`--output results/snapshot.png` のようにPNGの保存先を指定することもできます。

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

信号を追加せず、総需要と主線・サブの需要比を比較する Step 3 は次で実行します。

```bash
uv run python experiments/step03_demand_ratio/run.py
```

サブの合流待ちに応じて主線車両へ連続的に速度助言を与えた初期協調方式（Step 4-1）は次で再現できます。

```bash
uv run python experiments/step04-01_cooperative_merge/run.py
```

介入完了検知、最大介入時間、クールダウンを追加した改善版（Step 4-2）は次で実行します。

```bash
uv run python experiments/step04-02_cooperative_merge/run.py
```

主線・サブ別の待ち時間、ネットワーク内の未到着車両を含む Total Time Spent、需要条件別の SVG グラフを生成する Step 5-1 は次で実行します。

```bash
uv run python experiments/step05_metrics_visualization/run.py
```

道路へ入れずに待つ車両の挿入待ち時間まで TTS に含める Step 5-2 は次で実行します。

```bash
uv run python experiments/step05-02_insertion_wait_tts/run.py
```

Step 5-2の同一seed差と95%信頼区間を可視化する Step 5-3 は次で実行します。

```bash
uv run python experiments/step05-03_paired_confidence/run.py
```

Step 5-1〜5-3で当初の評価指標拡張・可視化要件を満たしたため、Step 5は完了しています。

サブ側を4 / 6 / 8秒の固定間隔で1台ずつ放流し、無制御・限定協調合流と完全版TTSの同一seed差で比較する Step 6 は次で実行します。

```bash
uv run python experiments/step06_ramp_metering/run.py
```

4秒間隔を主線混雑時だけ作動させる Step 6-2 は次で実行します。

```bash
uv run python experiments/step06-02_on_demand_ramp_metering/run.py
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
│   ├── step03_demand_ratio/
│   ├── step04-01_cooperative_merge/
│   ├── step04-02_cooperative_merge/
│   ├── step05_metrics_visualization/
│   ├── step05-02_insertion_wait_tts/
│   └── step05-03_paired_confidence/
├── tests/
└── main.py
```
