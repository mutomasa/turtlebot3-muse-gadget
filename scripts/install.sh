#!/usr/bin/env bash
# Install the Muse commands (and the optional resident bridge).
# Run with sudo from the repository root.
#   sudo scripts/install.sh [--restart] [--with-bridge]
#     --restart      restart the musegadget service afterwards
#     --with-bridge  install, enable and (re)start turtlebot3-muse-bridge.service
set -euo pipefail

PREFIX=/opt/turtlebot-muse
CMD_DIR=/etc/musegadget/commands.d
CONF_DIR=/etc/turtlebot-muse
BIN_DIR=/usr/local/bin
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT=turtlebot3-muse-bridge.service
RESTART=0
WITH_BRIDGE=0
for arg in "$@"; do
  case "$arg" in
    --restart) RESTART=1 ;;
    --with-bridge) WITH_BRIDGE=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }

install -d -m 755 "$PREFIX/lib" "$PREFIX/bin" "$CMD_DIR" "$CONF_DIR"
rm -rf "$PREFIX/lib/turtlebot3_muse"
cp -r "$REPO/src/turtlebot3_muse" "$PREFIX/lib/"
find "$PREFIX/lib" -name '__pycache__' -prune -exec rm -rf {} +
chmod -R a+rX,go-w "$PREFIX/lib"

install -m 644 "$REPO/scripts/ros_env.sh" "$PREFIX/bin/ros_env.sh"
for name in turtlebot-muse-status turtlebot-muse-map turtlebot-muse-bridge turtlebot-muse-bridge-ctl; do
  install -m 755 "$REPO/scripts/$name" "$PREFIX/bin/$name"
  ln -sf "$PREFIX/bin/$name" "$BIN_DIR/$name"
done

for cmd in robot.status robot.map; do
  install -m 644 "$REPO/commands/$cmd.json" "$CMD_DIR/$cmd.json"
done

if [[ ! -f "$CONF_DIR/robot.toml" ]]; then
  install -m 644 "$REPO/config/robot.toml" "$CONF_DIR/robot.toml"
else
  echo "keeping existing $CONF_DIR/robot.toml"
fi

/usr/bin/python3 -c 'import PIL' 2>/dev/null \
  || echo "WARN: python3-pil not found; robot.map needs: sudo apt install python3-pil" >&2

if [[ $WITH_BRIDGE -eq 1 ]]; then
  install -m 644 "$REPO/systemd/$UNIT" "/etc/systemd/system/$UNIT"
  systemctl daemon-reload
  systemctl enable "$UNIT"
  systemctl restart "$UNIT"
  systemctl --no-pager status "$UNIT" | head -n 5 || true
fi

if [[ $RESTART -eq 1 ]]; then
  systemctl restart musegadget
  journalctl -u musegadget -n 20 --no-pager
fi
echo "installed. test as the gadget user: sudo -u musebot $BIN_DIR/turtlebot-muse-status"
