# shellcheck shell=bash
# Shared ROS 2 environment for the Muse command wrappers.
# Values follow the workstation setup in turtlebot3_spatial_ai/work_hisotry.md.
# Any of them can be overridden from the environment (e.g. /etc/turtlebot-muse/env).

TURTLEBOT_MUSE_HOME="${TURTLEBOT_MUSE_HOME:-/opt/turtlebot-muse}"
TURTLEBOT_MUSE_CONFIG="${TURTLEBOT_MUSE_CONFIG:-/etc/turtlebot-muse/robot.toml}"
TURTLEBOT_MUSE_PYTHON="${TURTLEBOT_MUSE_PYTHON:-/usr/bin/python3}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

if [[ -f /etc/turtlebot-muse/env ]]; then
  # shellcheck disable=SC1091
  source /etc/turtlebot-muse/env
fi

# ROS setup scripts reference unset variables; never let them write to stdout.
set +u
# shellcheck disable=SC1090
source "$ROS_SETUP" >&2
set -u

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
# ROS_LOCALHOST_ONLY is deprecated on Jazzy; discovery is controlled by ROS_AUTOMATIC_DISCOVERY_RANGE.
export ROS_AUTOMATIC_DISCOVERY_RANGE="${ROS_AUTOMATIC_DISCOVERY_RANGE:-SUBNET}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
# Prefer the repository checkout's src/ when running from a clone.
_tbm_dir="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
if [[ -z "${TURTLEBOT_MUSE_LIB:-}" ]]; then
  if [[ -d "$_tbm_dir/../src/turtlebot3_muse" ]]; then
    TURTLEBOT_MUSE_LIB="$(readlink -f "$_tbm_dir/../src")"
  else
    TURTLEBOT_MUSE_LIB="$TURTLEBOT_MUSE_HOME/lib"
  fi
fi
export PYTHONPATH="${TURTLEBOT_MUSE_LIB}${PYTHONPATH:+:$PYTHONPATH}"
# Data files (RViz2 config): repository config/ or the installed share/.
if [[ -z "${TURTLEBOT_MUSE_SHARE:-}" ]]; then
  if [[ -d "$_tbm_dir/../config/rviz" ]]; then
    TURTLEBOT_MUSE_SHARE="$(readlink -f "$_tbm_dir/../config/rviz")"
  else
    TURTLEBOT_MUSE_SHARE="$TURTLEBOT_MUSE_HOME/share"
  fi
fi
export PYTHONDONTWRITEBYTECODE=1

turtlebot_muse_config_args() {
  if [[ -f "$TURTLEBOT_MUSE_CONFIG" ]]; then
    printf '%s\n' --config "$TURTLEBOT_MUSE_CONFIG"
  fi
}
