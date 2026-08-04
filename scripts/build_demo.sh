#!/usr/bin/env bash
# =============================================================================
# AssetsLab 交互式构建并测试 Godot Demo
#
# 流程:
#   1) 选择工作流实例 (run/workflows/<id>)
#   2) 确保制品存在 (dist/<id>) —— 缺失时可自动运行 export.artifacts 生成
#   3) 用 Godot 运行测试 demo:
#        [1] 窗口模式运行   godot --path prototype -- --artifacts dist/<id>
#        [2] Headless 冒烟   godot --path prototype --headless -- --artifacts dist/<id>
#
# 运行: ./scripts/build_demo.sh
# 环境变量: GODOT_BIN / GODOT_PATH (Godot 可执行), PYTHON_BIN (python 解释器)
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

PY=""
resolve_python() {
  local p="${PYTHON_BIN:-}"
  if [ -n "$p" ] && [ -x "$p" ]; then PY="$p"; return 0; fi
  if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; return 0; fi
  for c in python3 python; do
    if command -v "$c" >/dev/null 2>&1; then PY="$(command -v "$c")"; return 0; fi
  done
  return 1
}

# ----------------------------------------------------------------------------
# 实例列表: 从 run/workflows/ 收集, 按更新时间倒序
# ----------------------------------------------------------------------------
declare -a INSTANCES=()
load_instances() {
  INSTANCES=()
  local wf="$ROOT/run/workflows"
  [ -d "$wf" ] || return 1
  local d
  for d in "$wf"/*/; do
    [ -d "$d" ] || continue
    [ -f "$d/state.json" ] || continue
    INSTANCES+=("$(basename "$d")")
  done
  # 按 state.json 的 updated_at 倒序（缺失按名称）
  INSTANCES=($(for id in "${INSTANCES[@]}"; do
    local up
    up=$("$PY" -c "import json,sys; d=json.load(open('$ROOT/run/workflows/$id/state.json')); print(d.get('updated_at',''))" 2>/dev/null || echo "")
    echo "$up|$id"
  done | sort -r | cut -d'|' -f2))
}

has_artifacts() {
  [ -f "$ROOT/dist/$1/runtime_manifest.json" ]
}

show_instances() {
  echo
  info "${BOLD}可用工作流实例:${NC}"
  local i=1
  for id in "${INSTANCES[@]}"; do
    local mark="--"
    if has_artifacts "$id"; then mark="${GREEN}dist/$id ✓${NC}"; else mark="${YELLOW}无制品${NC}"; fi
    printf '  %2d) %-24s 制品: %b\n' "$i" "$id" "$mark"
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

ensure_artifacts() {
  local id="$1"
  if has_artifacts "$id"; then
    ok "制品已存在: dist/$id/"
    return 0
  fi
  warn "实例「$id」还没有导出制品（dist/$id/ 不存在）。"
  echo "  运行 export.artifacts 会执行工作流最后一步（需要前 5 步已通过）。"
  printf '  是否现在生成? [y/N] '
  local ans=""
  read -r ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    info "运行: $PY -m workflow run --workflow $id --action export.artifacts"
    "$PY" -m workflow run --workflow "$id" --action export.artifacts || {
      err "export.artifacts 运行失败（可能依赖步骤未通过）。"
      return 1
    }
    if has_artifacts "$id"; then ok "制品已生成: dist/$id/"; else err "制品仍未生成。"; return 1; fi
  else
    warn "跳过生成；没有制品时 demo 可能无法加载角色。"
  fi
  return 0
}

run_demo_menu() {
  local id="$1"
  while :; do
    echo
    info "${BOLD}实例: $id${NC}   制品: $ROOT/dist/$id"
    echo "  [1] 运行 Demo（Godot 窗口）"
    echo "  [2] Headless 冒烟测试（自动验证制品加载，Ctrl+C 结束）"
    echo "  [3] 重新导出制品（export.artifacts）"
    echo "  [4] 打开制品目录"
    echo "  [0] 返回"
    local c; c="$(choose_number "  请选择: " 4)"
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
        info "运行: $PY -m workflow run --workflow $id --action export.artifacts"
        "$PY" -m workflow run --workflow "$id" --action export.artifacts || err "export.artifacts 运行失败。"
        ;;
      4)
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
  echo "  AssetsLab — Godot Demo 构建与测试（交互式）"
  echo "=================================================="

  if ! resolve_godot; then
    err "未找到 Godot。请设置 GODOT_BIN/GODOT_PATH，或把 godot/godot4 加入 PATH，或放到相邻的 Godot-4.7/ 目录。"
    return 1
  fi
  if ! resolve_python; then
    err "未找到 Python。请设置 PYTHON_BIN，或使用项目 .venv。"
    return 1
  fi
  ok "Godot : $GODOT"
  ok "Python: $PY"

  if ! load_instances; then
    err "run/workflows/ 下没有实例。先创建实例: $PY -m workflow new --definition default --id <名字>"
    return 1
  fi

  while :; do
    show_instances
    local n
    n="$(choose_number "  请选择实例编号: " "${#INSTANCES[@]}")"
    [ "$n" = "0" ] && { echo "再见。"; return 0; }
    local sel="${INSTANCES[$((n - 1))]}"
    echo
    ok "已选实例: $sel"
    ensure_artifacts "$sel" || true
    run_demo_menu "$sel"
  done
}

main "$@"
