#!/usr/bin/env bash
# Check that the workstation actually receives TurtleBot3 data (not just topic names).
set -uo pipefail
source "$(dirname "$(readlink -f "$0")")/ros_env.sh"

echo "ROS_DOMAIN_ID=$ROS_DOMAIN_ID RMW_IMPLEMENTATION=$RMW_IMPLEMENTATION"
status=0
check_topic() {
  local topic=$1
  echo "== $topic"
  ros2 topic info "$topic" -v | grep -E 'Type|Node name|Reliability|Durability' || true
  if timeout 8 ros2 topic echo "$topic" --once --qos-reliability best_effort > /dev/null; then
    echo "   received: OK"
  else
    echo "   received: NO MESSAGE"; status=1
  fi
}
for topic in /odom /scan /battery_state; do check_topic "$topic"; done
echo "== TF odom -> base_link"
timeout 5 ros2 run tf2_ros tf2_echo odom base_link 2>&1 | head -n 4 || status=1
echo "== /map (optional)"
timeout 8 ros2 topic echo /map --once --qos-durability transient_local --field info > /dev/null \
  && echo "   received: OK" || echo "   received: NO MAP (SLAM / map_server not running)"
exit $status
