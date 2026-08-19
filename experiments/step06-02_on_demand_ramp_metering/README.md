# Step 6-2: 混雑時オンデマンドRamp Metering

Step 6の固定間隔制御は、ネットワーク内の混雑を軽減する条件でもサブ側の待ち時間を増やし、完全版TTSを改善しなかった。Step 6-2では4秒間隔の放流を常時適用せず、主線混雑時だけ作動させる。

## 制御ルール

- 観測対象: `main_in_0` の車両数と平均速度
- 作動: 主線車両が存在し、平均27 m/s以下が3秒継続
- 解除候補: 主線車両なし、または平均29 m/s以上が10秒継続
- 最短作動時間: 30秒
- 作動中の放流間隔: 4秒
- 新規制御対象: 停止位置まで130m以上の安全制動距離があるサブ車両
- 解除時: 保持中の全サブ車両を解放

27 / 29 m/sのヒステリシスと継続時間により、境界付近での頻繁なON/OFFを防ぐ。主線需要が低く同時に複数台が存在しない条件もあるため、台数ではなく通常走行30 m/sからの持続的な速度低下を主な作動信号とする。

## 比較戦略

- 無制御
- 限定協調合流
- 常時4秒Ramp Metering
- オンデマンド4秒Ramp Metering

```bash
uv run python experiments/step06-02_on_demand_ramp_metering/run.py
```

短時間の動作確認:

```bash
uv run python experiments/step06-02_on_demand_ramp_metering/run.py \
  --total-rates 1000 --demand-ratios 1:3 \
  --strategies uncontrolled,ramp_on_demand_4s \
  --duration 120 --clearance-time 60 --seeds 1,2
```

`results/`にはraw CSV、無制御との同一seed差、95%信頼区間、SVG、再現条件を出力する。raw CSVには作動回数、作動時間、作動時間比率、放流台数も含む。
