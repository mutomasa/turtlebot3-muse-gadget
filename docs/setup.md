# セットアップ手順

Ubuntu ワークステーション（Ubuntu 24.04・ROS 2 Jazzy）に Muse Gadget と本リポジトリのコマンドを導入する手順です。TurtleBot3 本体（ROS 2 Humble）には何も追加しません。

## 0. 前提

- TurtleBot3 本体で bringup が動いていること（`ros2 launch turtlebot3_bringup robot.launch.py`）
- 両方の端末で `ROS_DOMAIN_ID=30`
- ワークステーションに Bluetooth LE があること（Muse の初回ペアリングに必要）

BLE の有無は次のコマンドで確認できます。

```bash
bluetoothctl show | grep -E 'Controller|Powered'
```

何も表示されない場合、ワークステーションでは BLE を使えません。BLE 付きの別の Linux 機をガジェットホストにする構成を検討してください（設計書 1 章）。

## 1. ROS 2 の受信確認

```bash
git clone https://github.com/mutomasa/turtlebot3-muse-gadget.git
cd turtlebot3-muse-gadget
scripts/verify_ros2.sh
```

`/odom`、`/scan`、`/battery_state` がすべて `received: OK` になることを確認します。うまくいかない場合は [troubleshooting.md](troubleshooting.md) を参照してください。

ロボットが動いていれば、次のコマンドで `"state": "online"` が返ります。

```bash
scripts/turtlebot-muse-status --no-bridge
```

## 2. Gadget 用ユーザーの作成

Muse SDK は、そのユーザー権限でのシェル実行とファイル操作を Muse に許可します。専用の一般ユーザーを作り、sudo を与えないでください。

```bash
sudo adduser --disabled-password --gecos "Muse gadget" musebot
groups musebot   # sudo が含まれていないこと
```

## 3. Muse Gadget SDK の導入

1. [SDK トークン画面](https://gadgets.muse.ai/settings/sdk-tokens) でトークンを取得します。トークンは Git にコミットしないでください。
2. インストーラーを取得し、内容を確認してから実行します。

```bash
curl -fsSL https://raw.githubusercontent.com/facebookincubator/muse-gadget-sdk/main/linux/install.sh -o install.sh
less install.sh
bash install.sh --run-as musebot --sdk-token 'YOUR_SDK_TOKEN'
```

3. Muse アプリで Settings → Devices → Developer mode を有効にし、`MuseGadgetXXXXXX` をペアリングします。信頼できるネットワークで行ってください。
4. 状態を確認します。

```bash
musegadget doctor
systemctl status musegadget
journalctl -u musegadget -n 50 --no-pager
```

## 4. コマンドとブリッジの導入

```bash
sudo apt install python3-pil xvfb xauth ffmpeg   # robot.map / robot.view 用
sudo scripts/install.sh --with-bridge --with-viewer --restart
```

| オプション | 内容 |
| --- | --- |
| `--with-bridge` | 常駐ブリッジ `turtlebot3-muse-bridge.service` を導入・有効化・起動 |
| `--with-viewer` | `robot.view` 用の画面なし RViz2 `turtlebot3-muse-rviz.service` を導入・有効化・起動 |
| `--restart` | `musegadget` を再起動して、追加したコマンドを読み込ませる |

ブリッジなしでも `robot.status` は動きます（毎回ワンショット購読するため、応答に 1〜5 秒かかります）。

## 5. 動作確認

Gadget と同じユーザーで実行します。

```bash
sudo -u musebot /usr/local/bin/turtlebot-muse-status
sudo -u musebot /usr/local/bin/turtlebot-muse-bridge-ctl metrics
sudo -u musebot /usr/local/bin/turtlebot-muse-view --no-send --out /tmp/view.png
```

- `turtlebot-muse-status` の `source` が `ros2_bridge` ならブリッジ経由、`ros2_live` ならワンショット購読です。
- `metrics` で各トピックの受信数・最終受信からの秒数・受信レートを確認できます。

最後に Muse アプリから次のように指示します。

- 「`robot.status` を使って TurtleBot3 Burger の位置、向き、LiDAR の状態を教えて」
- 「`robot.map` で地図を送って」（`/map` が配信されている場合のみ）
- 「`robot.view` で RViz2 の画面を見せて」

## 設定の変更

| ファイル | 内容 |
| --- | --- |
| `/etc/turtlebot-muse/robot.toml` | トピック名、タイムアウト、鮮度の閾値、ソケットのパス |
| `/etc/turtlebot-muse/env` | 環境変数の上書き（例：`ROS_DOMAIN_ID=31`） |

変更後はブリッジを再起動します。

```bash
sudo systemctl restart turtlebot3-muse-bridge
```

画面なし RViz2 の固定フレームを `map` にする（SLAM や AMCL が動いている場合）：

```bash
sudo systemctl edit turtlebot3-muse-rviz
# [Service]
# Environment=TURTLEBOT_MUSE_RVIZ_FIXED_FRAME=map
sudo systemctl restart turtlebot3-muse-rviz
```

## アンインストール

```bash
sudo systemctl disable --now turtlebot3-muse-bridge turtlebot3-muse-rviz
sudo rm -f /etc/systemd/system/turtlebot3-muse-{bridge,rviz}.service
sudo rm -f /etc/musegadget/commands.d/robot.{status,map,view}.json
sudo rm -f /usr/local/bin/turtlebot-muse-{status,map,view,bridge,bridge-ctl,rviz}
sudo rm -rf /opt/turtlebot-muse /etc/turtlebot-muse
sudo systemctl daemon-reload && sudo systemctl restart musegadget
```
