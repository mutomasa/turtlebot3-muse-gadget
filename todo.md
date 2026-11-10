# TODO

[基本設計書](docs/basic_design.md) をもとにしたタスク一覧です。上から順に進めます。

## Phase 0：接続基盤（最優先）

### リポジトリ
- [x] リポジトリ `mutomasa/turtlebot3-muse-gadget` を作成し、設計書と README を配置
- [x] `pyproject.toml`、`.gitignore` を追加
- [x] `LICENSE` を追加（MIT）
- [x] `config/robot.toml`（トピック名、タイムアウト、鮮度閾値）を作成。追加依存を避けるため YAML ではなく TOML（標準ライブラリの `tomllib`）にした。`ROS_DOMAIN_ID` などはラッパーの環境変数で指定

### ROS 2 通信
- [ ] Humble（Burger）↔ Jazzy（ワークステーション）間で `/odom` と `/scan` の実メッセージを受信できることを確認
- [ ] `ros2 topic info -v` で各トピックの QoS を記録
- [ ] `tf2_echo odom base_link` で TF を確認
- [x] `scripts/verify_ros2.sh` を作成

### Muse Gadget SDK
- [ ] ワークステーションの BLE の有無を確認（なければ BLE 付き Linux 機をガジェットホストにする代替構成を検討）
- [ ] 非 sudo の専用ユーザー `musebot` を作成
- [ ] インストーラーの内容を確認したうえで SDK を導入
- [ ] Muse アプリの Developer mode で `MuseGadgetXXXXXX` をペアリング
- [ ] `musegadget doctor` と `journalctl -u musegadget` で状態を確認

### `robot.status` の実装
- [x] `commands/robot.status.json` を作成（`timeout_ms: 10000`）
- [x] ラッパー `scripts/turtlebot-muse-status` を作成（`/opt/ros/jazzy/setup.bash`、`ROS_DOMAIN_ID=30`、`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`、`ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET`、`/usr/bin/python3`）
- [x] `src/turtlebot3_muse/status_cli.py` を作成（設計書の `scripts/robot_status.py` に相当）
  - [x] `/odom` と `/scan` をワンショット購読（最大 4 秒待機）
  - [x] `/odom`・`/scan`・`/battery_state` に `qos_profile_sensor_data`（Best Effort は Reliable の publisher とも互換）
  - [x] `/battery_state` の電圧も返す（`state` の判定には使わない）
  - [x] 四元数から yaw 角を算出
  - [x] LiDAR 最短距離は `range_min <= r <= range_max` かつ有限値に限定し、有効値がなければ `null`
  - [x] `state` を `online` / `degraded` / `offline` / `unknown` で判定
  - [x] 欠落理由を分類（`timeout`、`no_scan`、`no_odom`、`stale`）
  - [x] 受信後の経過時間で鮮度を判定（時刻同期が不明な場合）
  - [x] ROS 2 コンテキストを `finally` で必ず終了
  - [x] 標準出力には JSON だけを出す
- [x] 開発用モックを用意（`source: mock` を明示）
- [x] `install.sh` を作成

### テスト
- [x] `tests/fixtures/odom.json`、`tests/fixtures/scan.json` を用意
- [x] JSON 契約テスト（パース可能、必須属性あり、標準出力が JSON のみ）
- [x] 四元数→yaw 変換と `frame_id` のテスト
- [x] LiDAR の `NaN`・`Inf`・範囲外値のテスト
- [x] 両系未着（`offline`/`unknown`）、片系欠落（`degraded`）のテスト
- [x] タイムアウトで無限待機しないことのテスト

### 実機検証
- [x] ROS 2 Jazzy 上で偽の publisher（隔離した `ROS_DOMAIN_ID`）を使い、`online` / `degraded` / `offline` と地図描画を E2E 確認
- [x] 同じ方法で常駐ブリッジを E2E 確認（応答約 0.25 秒、publisher 停止後に `offline`、ブリッジ停止時にワンショットへフォールバック）
- [ ] TurtleBot3 の bringup 起動中に `robot.status` が `online` を返すことを確認（2026-11-10 時点では bringup 停止中で、`offline` を正しく返すことのみ確認）
- [ ] Gadget 実行ユーザーの権限で `/usr/local/bin/turtlebot-muse-status` を実行し、JSON を確認
- [ ] Muse から自然言語で `robot.status` を呼び出し、位置・向き・LiDAR 状態が表示されることを確認
- [ ] LiDAR 停止・ネットワーク断の状態で、古いデータを現在値として返さないことを確認
- [ ] Gadget サービス再起動後に接続が再確立し、独自コマンドが登録されることを確認

## Phase 1：可視化と監視

- [x] `map_cli.py` / `map_renderer.py`：`/map`（OccupancyGrid）を PNG に変換
  - [x] unknown / free / occupied を識別
  - [x] 原点の回転、解像度、上下反転、地図サイズを考慮
  - [x] `map → base_link` の TF でロボット位置と向きを重畳（取得できなければ警告付きでマーカーなし）
  - [x] 2 MiB 以下に縮小・再圧縮
- [x] `/map` がないときは明確なエラーを返し、擬似地図を生成しない
- [x] `musegadget send-user-msg --image` での送信処理を実装（`robot.map` コマンドから送信）
- [ ] Muse 実機で画像送信を確認
- [x] `commands/robot.map.json` を追加
- [ ] カメラトピックを実機で確認し、存在する場合のみ静止画取得を実装（なければ「未設定」と表示）
- [x] 常駐ブリッジ（rclpy ノード + Unix domain socket）と状態キャッシュ。`robot.status` はブリッジを優先し、なければワンショット購読にフォールバック
- [x] 監視メトリクス：トピックごとの受信数・最終受信からの秒数・受信レート、op ごとの要求数（`turtlebot-muse-bridge-ctl metrics`）
- [ ] 監視メトリクスの残り：TF 成功率、SDK 再接続回数、コマンド失敗率、スナップショット生成時間
- [x] `systemd/turtlebot3-muse-bridge.service` を作成（`musebot` で実行、`ProtectSystem=strict` などで制限）
- [ ] 実機環境でブリッジを systemd で起動し、再起動・ロボット停止時の挙動を確認
- [x] `robot.view`：画面なし RViz2（Xvfb・読取専用設定）の画面を撮影して Muse チャットへ送信。`systemd/turtlebot3-muse-rviz.service` を追加
  - [x] ROS 2 Jazzy 上で偽データを使い、ロボット追従・LiDAR・Nav2 経路の表示と撮影を E2E 確認
  - [ ] 実機（bringup 起動中）で `robot.view` を確認
  - [ ] SLAM / AMCL 稼働時に固定フレームを `map` にして地図の表示を確認
- [ ] 認可済み要求だけを非同期キューで画像送信
- [x] 地図生成のテスト（占有値、回転、TF 欠落）

## Phase 2：ロボットアプリケーションのガジェット

- [ ] `commands/robot.scene_query.json` を追加
- [ ] `turtlebot3_spatial_ai` の Graph API または許可済み Neo4j 読取クエリに接続（任意の Cypher は実行させない）
- [ ] 回答に物体 ID、空間関係、座標系、最終観測時刻、信頼度を含める
- [ ] Scene Graph API の契約テスト
- [ ] Nav2 移動指示
  - [ ] 自然言語を「要求の提案」として解釈し、ユーザーの明示承認後に実行
  - [ ] `frame_id`、座標値、到達可能性、禁止領域、衝突余裕、位置・地図の鮮度を検証
  - [ ] `NavigateToPose` Action のみを使い、`/cmd_vel` を直接発行しない
  - [ ] 読取専用機能と実行権限を分離
  - [ ] タイムアウト、取消し、通信断時の動作を定義
  - [ ] 物理的な緊急停止手段を確保
- [ ] 行動結果と状態遷移を Muse に通知

## Phase 3：拡張ビュー

- [ ] RViz2 または Three.js / WebXR でロボットのライブビューを構築
- [ ] Muse との連携方式（URL 共有、画像通知、API 連携）を整理
- [ ] Muse 公式 SDK に独自 UI 機構が追加された場合のみ、ネイティブ埋め込みを再評価

## ドキュメント

- [x] `docs/setup.md`
- [x] `docs/troubleshooting.md`
- [x] `docs/security.md`
- [x] `docs/interfaces.md`
