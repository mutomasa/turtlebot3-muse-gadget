# セキュリティと安全性

## 権限

| コンポーネント | 実行ユーザー | 権限 |
| --- | --- | --- |
| Muse Gadget（`musegadget`） | `musebot` | 一般ユーザー。sudo なし |
| `robot.status` / `robot.map` | `musebot`（Gadget から起動） | ROS 2 の購読、`musegadget send-user-msg` |
| 常駐ブリッジ | `musebot`（systemd） | ROS 2 の購読、`/run/turtlebot-muse` への書き込みだけ |

- Muse SDK は、そのユーザー権限でのシェル実行（`system.run`）とファイル操作を Muse に許可します。`musebot` に sudo を与えず、開発用アカウントで Gadget を動かさないでください。
- ブリッジの systemd ユニットは `ProtectSystem=strict`、`ProtectHome=read-only`、`NoNewPrivileges=yes` などで書き込み先を制限しています。

## ロボットを動かさない

- `robot.status`、`robot.map`、ブリッジは**購読だけ**を行い、ROS 2 へは何も publish しません。`/cmd_vel` も使いません。
- 将来の移動指示（P2）は Nav2 の `NavigateToPose` Action を通し、ユーザーの明示的な承認と、目標地点の検証を必須にします。LLM から `/cmd_vel` を直接出すことはしません。
- `/cmd_vel` にゼロを送ることは緊急停止の代わりになりません。物理的に止める手段（電源）を常に確保してください。
- 作業履歴にあるとおり、`/motor_power` を有効にした直後に古い `/cmd_vel` でロボットが動いたことがあります。テストで ROS 2 にデータを流すときは、ロボットと別の `ROS_DOMAIN_ID` を使ってください（本リポジトリの E2E 確認では 77 を使用）。

## ネットワーク

- DDS には認証がありません。同じドメインの LAN 上の端末は、すべてのトピックを読み書きできます。信頼できるネットワークでのみ使ってください。
- ブリッジは TCP ポートを開きません。Unix ドメインソケット（`/run/turtlebot-muse/bridge.sock`、モード 0600、ディレクトリ 0750）だけを使います。
- ROS Bridge の WebSocket などをインターネットに公開しないでください。

## 秘密情報

- SDK トークンやセッション情報を、ログ・Git・Issue に残さないでください。`.gitignore` で `*.token` と `.env` を除外しています。
- ペアリングは信頼できるネットワークで行ってください。

## プライバシー

- 地図やカメラ画像には、部屋の様子や人が写ることがあります。`robot.map` は Muse チャットへ画像を送ります。送り先と記録の扱いを確認してから使ってください。
- 地図画像は一時ファイル（`$XDG_RUNTIME_DIR` または `/tmp`）に保存し、上書きします。

## 応答の正確さ

- ROS 2 の受信に失敗したとき、サンプル値を返しません。開発用モックは必ず `source: mock` と表示し、地図画像の説明文にも `[MOCK]` を付けます。
- 古いデータは `fresh: false` と警告で明示し、すべて古ければ `state: offline` にします。
- `/odom` の位置は `odom` フレームの値で、地図上の絶対位置ではありません（`odom.note` に明記）。
