# インターフェース仕様

Muse コマンドは標準入力で JSON オブジェクト（パラメータ）を受け取り、標準出力に JSON オブジェクトを 1 つだけ返します。ログはすべて標準エラー出力に出します。エラー時も終了コードは 0 で、内容は JSON の `state` と `error` で表します。

## `robot.status`

読取専用。`/odom`、`/scan`、`/battery_state` を Best Effort でワンショット購読します。`/odom` と `/scan` がそろうか、`status.wait_timeout_s`（既定 4 秒）が経過するまで待ちます。各トピックは最後に受信したメッセージを使います。

### `state`

| 値 | 条件 |
| --- | --- |
| `online` | `/odom` と `/scan` を受信し、どちらも新鮮で、LiDAR に有効な距離値がある |
| `degraded` | 何かは受信したが、上の条件を満たさない |
| `offline` | 待機時間内に `/odom` も `/scan` も受信できなかった |
| `unknown` | 収集処理そのものが失敗した（`error` を参照） |

`/battery_state` は `state` の判定に使いません。

### 鮮度

- **新鮮（fresh）**：最後の受信からの経過時間（単調時計）が `status.max_age_s`（既定 2 秒）以下
- ヘッダ時刻と壁時計の差が `status.max_stamp_skew_s`（既定 5 秒）を超えると `<topic>_stamp_skew` を警告します。ロボットとワークステーションの時刻同期を前提にできないため、鮮度の判定には使いません。

### フィールド

| フィールド | 説明 |
| --- | --- |
| `source` | `ros2_live` または `mock` |
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
| `timeout` | `/odom` と `/scan` がそろう前に待機時間が終わった |
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
