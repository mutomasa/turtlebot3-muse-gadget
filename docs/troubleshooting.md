# トラブルシューティング

まず `robot.status` の `state` と `warnings` を見て、どこで止まっているかを切り分けます。

| 症状 | 見る場所 |
| --- | --- |
| Muse がコマンドを認識しない | Muse SDK（下の「Muse 側」） |
| `state: offline` | ROS 2 の受信（下の「ROS 2 側」） |
| `state: degraded` | `warnings` に出ているトピック |
| `state: unknown` | `error.code` と `error.message` |
| `robot.map` が `no_map` | SLAM / map_server |

## ROS 2 側

### `offline`：何も受信できない

1. ロボットの bringup が動いているか確認します。`ros2 topic list` にトピック名が出ても、publisher がいるとは限りません。

```bash
ros2 topic info /odom    # Publisher count: 0 なら bringup が止まっている
```

2. 環境変数が両方の端末で一致しているか確認します。

```bash
printenv | grep -E 'ROS_DOMAIN_ID|RMW_IMPLEMENTATION|ROS_AUTOMATIC_DISCOVERY_RANGE'
```

3. `scripts/verify_ros2.sh` で、実メッセージを受信できるか確認します。
4. ファイアウォールが DDS（UDP 7400 番台）を止めていないか確認します。

### `degraded` と警告

| 警告 | 原因の候補 |
| --- | --- |
| `no_scan` | LiDAR の電源・ケーブル、`LDS_MODEL`、ドライバ |
| `no_valid_scan_ranges` | すべての点が範囲外（センサーを覆っている、極端に開けた場所） |
| `stale_odom`, `stale_scan` | 受信が途切れた。ネットワーク・Wi-Fi の状態を確認 |
| `odom_stamp_skew` | ロボットとワークステーションの時刻がずれている。鮮度判定には影響しない。`chrony` などで時刻同期を推奨 |
| `no_battery` | `/battery_state` が来ていない。状態判定には影響しない |

### QoS の不一致

本ツールは `/odom`・`/scan`・`/battery_state` を Best Effort で購読するので、publisher が Reliable でも Best Effort でも受信できます。`/map` は Reliable・Transient Local で購読します。map の publisher が Volatile の場合は `robot.toml` の `[map] transient_local = false` にします。

## ブリッジ

```bash
systemctl status turtlebot3-muse-bridge
journalctl -u turtlebot3-muse-bridge -n 50 --no-pager
sudo -u musebot turtlebot-muse-bridge-ctl metrics
```

| 症状 | 対応 |
| --- | --- |
| `source` が `ros2_live` のまま | ブリッジが止まっているか、ソケットに接続できない。ワンショット購読で動作は続く |
| `another server is already listening` | ブリッジが二重に起動している |
| `Permission denied` | `musebot` 以外のユーザーで実行している。ソケットは `musebot` だけが使える |
| `metrics` の `count` が増えない | ブリッジは動いているが ROS 2 を受信できていない（上の「ROS 2 側」） |

## Muse 側

```bash
musegadget doctor
journalctl -u musegadget -n 50 --no-pager
ls -l /etc/musegadget/commands.d/
```

| 症状 | 対応 |
| --- | --- |
| コマンドが一覧に出ない | JSON の構文、ファイル名、`systemctl restart musegadget` |
| JSON パースエラー | `sudo -u musebot /usr/local/bin/turtlebot-muse-status` の標準出力が JSON 1 行だけか確認 |
| タイムアウト | `robot.status` は 10 秒、`robot.map` は 30 秒。ブリッジを使うと短くなる |
| 画像が届かない | `robot.map` の結果の `sent` と `send_error` を確認。画像の作成と送信は別に診断する |

## 地図（`robot.map`）

| 状態・警告 | 原因の候補 |
| --- | --- |
| `no_map` | SLAM（cartographer / slam_toolbox）や map_server が `/map` を配信していない |
| `robot_pose_unavailable` | `map → base_link` の TF がない。SLAM やローカライゼーション（AMCL）が動いていない |
| `robot_outside_map` | 地図とロボット位置が合っていない。初期位置の設定を確認 |
| `robot_pose_old` | TF が更新されていない |
