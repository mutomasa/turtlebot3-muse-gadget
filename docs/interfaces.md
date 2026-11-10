# インターフェース仕様

Muse コマンドは標準入力で JSON オブジェクト（パラメータ）を受け取り、標準出力に JSON オブジェクトを 1 つだけ返します。ログはすべて標準エラー出力に出します。エラー時も終了コードは 0 で、内容は JSON の `state` と `error` で表します。

## `robot.status`

読取専用。状態は次の順で取得します。

1. **常駐ブリッジ**（`source: ros2_bridge`）：`bridge.socket_path` のソケットがあれば問い合わせます（`bridge.request_timeout_s`、既定 1 秒）。
2. **ワンショット購読**（`source: ros2_live`）：ブリッジがない、または応答がない場合に、`/odom`、`/scan`、`/battery_state` を Best Effort で購読します。`/odom` と `/scan` がそろうか、`status.wait_timeout_s`（既定 4 秒）が経過するまで待ちます。

どちらも、各トピックで最後に受信したメッセージを使います。`--no-bridge` を付けると常にワンショット購読します。

### `state`

| 値 | 条件 |
| --- | --- |
| `online` | `/odom` と `/scan` を受信し、どちらも新鮮で、LiDAR に有効な距離値がある |
| `degraded` | 何かは受信したが、上の条件を満たさない |
| `offline` | 新しいデータがない（`/odom` も `/scan` も未受信、または受信済みのものがすべて古い） |
| `unknown` | 収集処理そのものが失敗した（`error` を参照） |

`/battery_state` は `state` の判定に使いません。

### 鮮度

- **新鮮（fresh）**：最後の受信からの経過時間（単調時計）が `status.max_age_s`（既定 2 秒）以下
- ヘッダ時刻と壁時計の差が `status.max_stamp_skew_s`（既定 5 秒）を超えると `<topic>_stamp_skew` を警告します。ロボットとワークステーションの時刻同期を前提にできないため、鮮度の判定には使いません。

### フィールド

| フィールド | 説明 |
| --- | --- |
| `source` | `ros2_bridge`、`ros2_live`、`mock` のいずれか |
| `observed_at` | 応答を作った時刻（UTC、ISO 8601） |
| `odom.x_m`, `odom.y_m`, `odom.yaw_deg` | `odom` フレームでの位置と向き。地図上の絶対位置ではない（`odom.note`） |
| `odom.linear_x_mps`, `odom.angular_z_radps` | 速度 |
| `lidar.min_distance_m` | `range_min ≤ r ≤ range_max` かつ有限な値の最小値。有効値がなければ `null` |
| `lidar.valid_points`, `lidar.total_points` | 有効点数 / 全点数（LDS-03 は 400 点） |
| `battery.voltage_v` | 電圧 |
| `battery.percentage_raw` | `BatteryState.percentage` をそのまま返す（NaN は `null`） |
| `*.age_s`, `*.fresh` | 受信からの経過秒と鮮度 |

未受信のセクションは `received: false` で、数値はすべて `null` です。

### `warnings`

| コード | 意味 |
| --- | --- |
| `timeout` | `/odom` と `/scan` がそろう前に待機時間が終わった（ワンショット購読のみ） |
| `no_odom`, `no_scan`, `no_battery` | 未受信 |
| `no_valid_scan_ranges` | `/scan` を受信したが有効な距離値がない |
| `stale_odom`, `stale_scan`, `stale_battery` | 受信したが古い |
| `odom_stamp_skew` など | ヘッダ時刻と壁時計がずれている |
| `config_error`, `invalid_params`, `collection_error` | `state: unknown` のときの原因 |

## `robot.map`

読取専用。`/map`（Reliable・Transient Local）を待ち、受信できたら `map → base_link` の TF を探してロボット位置を重畳し、PNG を Muse チャットへ送ります。

- 画像は地図グリッドの向きで描きます（グリッドの +x が右、+y が上）。
- 色：占有（≥65）は黒、自由（≤25）は白、不明は灰色、その間は濃淡。ロボットは赤い円と向きの線。
- 画像は `map.max_image_bytes`（既定 2 MiB）以下になるまで縮小します。
- `/map` を受信できなければ `state: no_map` を返し、画像は作りません。

### `state`

| 値 | 意味 |
| --- | --- |
| `ok` | 画像を作成した（送信結果は `sent`） |
| `no_map` | `/map` を受信できなかった |
| `error` | 処理が失敗した（`error` を参照） |

### `warnings`

| コード | 意味 |
| --- | --- |
| `no_map`, `timeout` | 地図を受信できなかった |
| `robot_pose_unavailable` | TF が取れず、位置マーカーなしで描画した |
| `robot_outside_map` | ロボット位置が地図の外 |
| `robot_pose_old` | TF の時刻が古い |
| `send_failed` | `musegadget send-user-msg` が失敗した（`send_error` に詳細） |

## `robot.view`

画面なしの RViz2（`turtlebot3-muse-rviz.service`）の画面を 1 枚撮り、Muse チャットへ送ります。Muse チャットは静止画しか扱えないため、呼び出しごとに 1 枚です。

- RViz2 は専用の Xvfb ディスプレイ（既定 `:99`）で、`config/rviz/muse_view.rviz` を使って動きます。デスクトップの RViz2 には触れません。
- 表示：上から見下ろす正射影で、`base_link` を中心に追従します。グリッド 0.5 m、地図、Nav2 の経路（`/plan`）、ロボットモデル、ロボットの座標軸、LiDAR（ピンク）。
- 固定フレームは既定で `odom` です。SLAM や AMCL が `map → odom` を出すようになったら、サービスの `TURTLEBOT_MUSE_RVIZ_FIXED_FRAME=map` に変えます。
- 設定のツールは Interact だけです。Goal や初期位置を送るツールはなく、この RViz2 から ROS 2 へ指令は出ません。
- 撮影前にロボットの状態（`robot.status` と同じ）を確認し、`online` でなければ説明文に「表示が最新ではない可能性があります」と付けます。

### `state`

| 値 | 意味 |
| --- | --- |
| `ok` | 撮影した（送信結果は `sent`） |
| `viewer_unavailable` | 画面なし RViz2 が動いていない（X ディスプレイがない） |
| `viewer_not_ready` | 画面が真っ黒など単色で、RViz2 がまだ描画していない。送信しない |
| `error` | 撮影などが失敗した（`error.code` は `capture_error` など） |

### フィールドと警告

| フィールド | 説明 |
| --- | --- |
| `robot_state` | 撮影時のロボットの `state`（`online` など） |
| `robot_warnings` | そのときの `robot.status` の警告 |
| `image` | 保存した PNG のパス・サイズ（2 MiB 以下） |
| `warnings` | `robot_not_online`、`blank_frame`、`send_failed`、`viewer_unavailable` |

## 常駐ブリッジの IPC

`/run/turtlebot-muse/bridge.sock`（Unix ドメインソケット、モード 0600）で、改行区切りの JSON を 1 往復だけやり取りします。

要求：

```json
{"op": "status"}
```

応答：

```json
{"ok": true, "result": { ... }}
{"ok": false, "error": "ValueError: unknown op: 'move'"}
```

| `op` | `result` |
| --- | --- |
| `status` | `robot.status` と同じ形式（`source: ros2_bridge`） |
| `metrics` | `uptime_s`、トピックごとの `count`・`age_s`・`rate_hz`、`requests`（op ごとの要求数） |
| `ping` | `{"pong": true}` |

運用時は `turtlebot-muse-bridge-ctl {status|metrics|ping}` で確認できます。
