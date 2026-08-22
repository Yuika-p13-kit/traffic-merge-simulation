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
- v3 Step 1 Qiita原稿: `docs/qiita_highway_merge_v3_step01.md`
- v3 Step 2 Qiita原稿: `docs/qiita_highway_merge_v3_step02.md`
- v3 Step 3 Qiita原稿: `docs/qiita_highway_merge_v3_step03.md`

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

### Python 3.13 でのモジュール実行

Python 3.13 では、現在の `uv` が作るeditableインストール用の
`__editable__.*.pth` をPythonが読み飛ばし、`src/traffic_merge_sim` を
見つけられないことがある。その場合は `uv sync --reinstall-package` を
繰り返さず、モジュール実行時に `PYTHONPATH=src` を付ける。

```bash
PYTHONPATH=src uv run python -m traffic_merge_sim.animate --help
```

`uv sync --no-editable` はこのリポジトリでは使用しない。モジュール自体は
読み込めても、パッケージ外の `sumo/` ネットワーク資産を見つけられなくなる。

## 最小無制御合流モデル

現在の最小モデルは、主線 1 車線・従線 1 車線・合流後 1 車線の単純な構成です。

- 主線: 1000 veh/h
- 従線: 400 veh/h
- 車種: 1 種類
- 信号: なし
- Ramp Metering: なし

## 高速道路型合流モデル（v3）

現行の研究系列は `highway_merge_v3` を使います。主線（上流2車線）、ランプ、600 m の3車線合流区間、下流2車線を明示したネットワークです。旧 `minimal_merge` および試作の `highway_merge_v2` と結果・監視区間を共有しません。

- ネットワーク: `sumo/network/highway_merge_v3.net.xml`
- ネットワーク設定と監視区間: `src/traffic_merge_sim/network_config.py`
- 無制御ケースのPython入口: `traffic_merge_sim.highway_merge.run_highway_v3_single_case`

Step 1〜2 は完了し、Step 3で需要配分を比較する。Step 4〜6の制御実験は、その後に本系列専用として追加する。

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
PYTHONPATH=src uv run python -m traffic_merge_sim.visualize \
  --main-rate 200 --side-rate 820 --duration 600 --seed 42 --time 300
```

高速道路型ネットワークを描画する場合は、`--network highway_merge_v3` を指定します。画像とFCDはネットワーク名ごとの出力先に分離されます。

既定では、FCD中間データとPNGを `sumo/output/generated/visualization/` に生成します。このディレクトリはGit管理対象外なので、同じコマンドでいつでも再生成できます。`--output results/snapshot.png` のようにPNGの保存先を指定することもできます。

### 合流状態のアニメーション可視化

FCD出力を使い、道路形状と車両移動をMP4（既定）またはGIFとして保存できます。主線車両は青、ランプ車両は赤で表示します。

```bash
PYTHONPATH=src uv run python -m traffic_merge_sim.animate \
  --network highway_merge_v3 --main-rate 1800 --side-rate 2150 \
  --duration 120 --start-time 30 --end-time 90 --fps 10
```

GIFを作成するには `--format gif` を指定します。FCDの全時刻を使う代わりに間引く場合は `--frame-step 2` のように指定できます。既定では出力を `sumo/output/generated/visualization/<network>/` に保存します。`--output results/merge.gif --format gif` のように明示的な保存先も指定できます。

既存のシミュレーション結果を再実行せずに可視化するには、実行時にSUMOのFCD軌跡を保存し、`--fcd-input` を指定します。例えばv3 Step 4では次のように、結果CSVとは別にGit管理外の軌跡を保存できます。

```bash
uv run python experiments/highway_merge_v3/step04_cooperative_merge/run.py \
  --total-rates 3950 --demand-ratios 1:1 --strategies uncontrolled,cooperative_limited \
  --seeds 1 --fcd-output-dir sumo/output/generated/trajectories/v3-step04

PYTHONPATH=src uv run python -m traffic_merge_sim.animate \
  --network highway_merge_v3 \
  --fcd-input sumo/output/generated/trajectories/v3-step04/cooperative_limited_main_1975_ramp_1975_seed_1.fcd.xml \
  --start-time 30 --end-time 120 --frame-step 2 --fps 10 --format gif \
  --output sumo/output/generated/visualization/v3-step04-cooperative.gif
```

FCDとGIFは `sumo/output/generated/` 配下に置くためGit管理外です。各実験の実行器は、必要なときだけFCD出力先を受け取る設計にし、通常の一括評価で大きな軌跡ファイルを作らないようにします。

### 3. v3 Step 1: 無制御ベースライン

```bash
uv run python experiments/highway_merge_v3/step01_baseline/run.py
```

この実験は主線・ランプ需要の初期範囲で、流出完了・衝突・テレポートを確認する。結果は `experiments/highway_merge_v3/step01_baseline/results/` に保存する。

### 4. v3 Step 2: 無制御時の容量境界

```bash
uv run python experiments/highway_merge_v3/step02_throughput/run.py
```

主線1,800 veh/hを固定し、ランプ需要を増やして、クリアランス終了後の未完了車両が残る境界を測定する。結果は `experiments/highway_merge_v3/step02_throughput/results/` に保存する。

### 5. v3 Step 3: 無制御時の需要比比較

```bash
PYTHONPATH=src uv run python experiments/highway_merge_v3/step03_demand_ratio/run.py
```

Step 2で得た境界付近の総需要3,950 / 4,000 veh/hを固定し、主線:ランプ需要比1:1〜1:5を比較する。結果は `experiments/highway_merge_v3/step03_demand_ratio/results/` に保存する。

### 6. 旧 `minimal_merge` 系列の再現用スイープ

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
