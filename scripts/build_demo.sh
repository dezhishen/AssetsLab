#!/usr/bin/env bash
# =============================================================================
# AssetsLab 基于 dist 制品的 Godot Demo 构建/运行（交互式）
#
# 直接依赖 dist/<id>/ 制品包（不再依赖工作流实例 / export.artifacts 流程）：
#   1) 扫描 dist/ 下的制品包
#   2) 选择制品
#   3) 用 Godot 运行测试 demo:
#        [1] 窗口模式运行   godot --path prototype -- --artifacts dist/<id>
#        [2] Headless 冒烟   godot --path prototype --headless -- --artifacts dist/<id>
#
# 运行: ./scripts/build_demo.sh
# 环境变量: GODOT_BIN / GODOT_PATH (Godot 可执行)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info(){ echo -e "${CYAN}[i]${NC} $*"; }
ok(){   echo -e "${GREEN}[ok]${NC} $*"; }
warn(){ echo -e "${YELLOW}[!]${NC} $*"; }
err(){  echo -e "${RED}[x]${NC} $*" >&2; }

# ----------------------------------------------------------------------------
# 工具探测
# ----------------------------------------------------------------------------
GODOT=""
resolve_godot() {
  local g="${GODOT_BIN:-${GODOT_PATH:-}}"
  if [ -n "$g" ]; then
    if command -v "$g" >/dev/null 2>&1; then GODOT="$(command -v "$g")"; return 0; fi
    if [ -f "$g" ] && [ -x "$g" ]; then GODOT="$g"; return 0; fi
  fi
  for c in godot4 godot; do
    if command -v "$c" >/dev/null 2>&1; then GODOT="$(command -v "$c")"; return 0; fi
  done
  local base="$ROOT/../Godot-4.7"
  if [ -d "$base" ]; then
    local f
    while IFS= read -r f; do
      [ -x "$f" ] && GODOT="$f" && return 0
    done < <(find "$base" -type f 2>/dev/null | grep -iE 'godot|x86_64' | head -20)
  fi
  return 1
}

# ----------------------------------------------------------------------------
# 制品列表: 从 dist/ 收集（依赖制品，不依赖工作流实例/流程）
# ----------------------------------------------------------------------------
declare -a ARTIFACTS=()
load_artifacts() {
  ARTIFACTS=()
  local d
  for d in "$ROOT"/dist/*/; do
    [ -d "$d" ] || continue
    ARTIFACTS+=("$(basename "$d")")
  done
  ARTIFACTS=($(printf '%s\n' "${ARTIFACTS[@]}" | sort))
}

has_manifest() { [ -f "$ROOT/dist/$1/runtime_manifest.json" ]; }

show_artifacts() {
  echo
  info "${BOLD}可用制品包 (dist/):${NC}"
  local i=1
  for id in "${ARTIFACTS[@]}"; do
    local mark="--"
    if has_manifest "$id"; then mark="${GREEN}runtime_manifest ✓${NC}"; else mark="${YELLOW}无 manifest${NC}"; fi
    printf '  %2d) %-24s %b\n' "$i" "$id" "$mark"
    i=$((i + 1))
  done
  echo "    0) 退出"
}

choose_number() {
  local prompt="$1" max="$2"
  local n=""
  while :; do
    printf '%s ' "$prompt" >&2
    read -r n
    [ -z "$n" ] && continue
    if [ "$n" = "0" ]; then echo "0"; return 0; fi
    if [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le "$max" ]; then
      echo "$n"; return 0
    fi
    warn "请输入 1-$max 之间的数字（0 取消）。" >&2
  done
}

run_demo_menu() {
  local id="$1"
  while :; do
    echo
    info "${BOLD}制品: $id${NC}   $ROOT/dist/$id"
    echo "  [1] 运行 Demo（Godot 窗口）"
    echo "  [2] Headless 冒烟测试（Ctrl+C 结束）"
    echo "  [3] 打开制品目录"
    echo "  [0] 返回"
    local c; c="$(choose_number "  请选择: " 3)"
    [ "$c" = "0" ] && return 0
    case "$c" in
      1)
        info "运行: $GODOT --path prototype -- --artifacts dist/$id"
        "$GODOT" --path prototype -- --artifacts "dist/$id"
        ;;
      2)
        info "运行 headless 冒烟: $GODOT --path prototype --headless -- --artifacts dist/$id"
        warn "按 Ctrl+C 结束测试。"
        "$GODOT" --path prototype --headless -- --artifacts "dist/$id" || true
        ;;
      3)
        if [ -d "$ROOT/dist/$id" ]; then
          (cd "$ROOT/dist/$id" && "$SHELL") || true
        else
          warn "dist/$id 不存在。"
        fi
        ;;
    esac
  done
}

# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
main() {
  echo
  echo "=================================================="
  echo "  AssetsLab — Godot Demo 构建与测试（制品驱动）"
  echo "=================================================="

  if ! resolve_godot; then
    err "未找到 Godot。请设置 GODOT_BIN/GODOT_PATH，或把 godot/godot4 加入 PATH，或放到相邻的 Godot-4.7/ 目录。"
    return 1
  fi
  ok "Godot : $GODOT"

  if ! load_artifacts || [ "${#ARTIFACTS[@]}" -eq 0 ]; then
    err "dist/ 下没有制品包。请先导出制品（例如通过工作流实例 export.artifacts），或直接把制品包放到 dist/ 下。"
    return 1
  fi

  while :; do
    show_artifacts
    local n
    n="$(choose_number "  请选择制品编号: " "${#ARTIFACTS[@]}")"
    [ "$n" = "0" ] && { echo "再见。"; return 0; }
    local sel="${ARTIFACTS[$((n - 1))]}"
    echo
    ok "已选制品: $sel"
    run_demo_menu "$sel"
  done
}

main "$@"
