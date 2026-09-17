#!/bin/sh

# ==================== 基础配置区域 ====================
REPO_OWNER="MetaCubeX"
REPO_NAME="mihomo"
TMP_DIR="/tmp/mihomo_update"

# 保留备份文件数量
KEEP_BACKUPS=3

# GitHub Token 配置（可留空，或从环境变量传入）
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
# ====================================================

# 显示帮助信息
show_help() {
    cat << EOF
用法: $0 [选项]

目标应用选择 (共存时建议显式指定):
      --nikki           指定更新 Nikki 核心 (/usr/bin/mihomo)
      --openclash       指定更新 OpenClash Meta 核心 (/etc/openclash/core/clash_meta)

通道与更新选项:
  (无参数)              跟随当前核心通道自动更新
  -s, --switch          反转通道 (Release <-> Alpha 互切)
      --alpha           强制安装/更新至最新 Alpha 预发布版本
      --release         强制安装/更新至最新 Release 稳定版本
      --stable          同 --release
  -h, --help            显示此帮助信息
EOF
}

# ==================== 1. 参数解析 ====================
OP_MODE="default"
TARGET_APP=""

while [ $# -gt 0 ]; do
    case "$1" in
        -s|--switch)
            OP_MODE="switch"
            shift
            ;;
        --alpha)
            OP_MODE="alpha"
            shift
            ;;
        --release|--stable)
            OP_MODE="stable"
            shift
            ;;
        --nikki)
            TARGET_APP="nikki"
            shift
            ;;
        --openclash)
            TARGET_APP="openclash"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "错误: 未知参数 '$1'"
            show_help
            exit 1
            ;;
    esac
done

# ==================== 2. 动态环境检测逻辑 ====================
detect_environment() {
    # 1. 用户显式指定目标
    if [ "$TARGET_APP" = "nikki" ]; then
        ENV_TYPE="nikki"
        LOCAL_BIN_PATH="/usr/bin/mihomo"
        SERVICE_STOP="/etc/init.d/nikki stop"
        SERVICE_START="/etc/init.d/nikki start"
        return
    elif [ "$TARGET_APP" = "openclash" ]; then
        ENV_TYPE="openclash"
        LOCAL_BIN_PATH="/etc/openclash/core/clash_meta"
        SERVICE_STOP="/etc/init.d/openclash stop"
        SERVICE_START="/etc/init.d/openclash start"
        return
    fi

    # 2. 检查两者是否同时安装
    HAS_NIKKI=0
    HAS_OPENCLASH=0
    [ -f "/etc/init.d/nikki" ] && HAS_NIKKI=1
    [ -f "/etc/init.d/openclash" ] && HAS_OPENCLASH=1

    if [ $HAS_NIKKI -eq 1 ] && [ $HAS_OPENCLASH -eq 1 ]; then
        echo "提示: 检测到系统中同时安装了 Nikki 与 OpenClash"

        NIKKI_RUNNING=$(pgrep -f "/usr/bin/mihomo" 2>/dev/null)
        OC_RUNNING=$(pgrep -f "clash_meta" 2>/dev/null)

        if [ -n "$NIKKI_RUNNING" ] && [ -z "$OC_RUNNING" ]; then
            echo ">> 检测到 Nikki 正在运行，自动选择更新 Nikki"
            TARGET_APP="nikki"
        elif [ -n "$OC_RUNNING" ] && [ -z "$NIKKI_RUNNING" ]; then
            echo ">> 检测到 OpenClash 正在运行，自动选择更新 OpenClash"
            TARGET_APP="openclash"
        else
            echo ">> 两者均在运行或均未运行，默认选择 Nikki。"
            echo ">> 如需更新 OpenClash，请使用参数: $0 --openclash"
            TARGET_APP="nikki"
        fi

        detect_environment
        return
    fi

    # 3. 单独安装或通用 Linux 环境判定
    if [ $HAS_NIKKI -eq 1 ]; then
        ENV_TYPE="nikki"
        LOCAL_BIN_PATH="/usr/bin/mihomo"
        SERVICE_STOP="/etc/init.d/nikki stop"
        SERVICE_START="/etc/init.d/nikki start"
    elif [ $HAS_OPENCLASH -eq 1 ]; then
        ENV_TYPE="openclash"
        LOCAL_BIN_PATH="/etc/openclash/core/clash_meta"
        SERVICE_STOP="/etc/init.d/openclash stop"
        SERVICE_START="/etc/init.d/openclash start"
    else
        ENV_TYPE="linux"
        [ -f "/usr/local/bin/mihomo" ] && LOCAL_BIN_PATH="/usr/local/bin/mihomo" || LOCAL_BIN_PATH="/usr/bin/mihomo"
        if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -qE '^mihomo\.service'; then
            SERVICE_STOP="systemctl stop mihomo"
            SERVICE_START="systemctl start mihomo"
        else
            SERVICE_STOP=""
            SERVICE_START=""
        fi
    fi
}

detect_environment
echo "=========================================="
echo "环境检测结果: $ENV_TYPE"
echo "目标核心路径: $LOCAL_BIN_PATH"
[ -n "$SERVICE_STOP" ] && echo "关联服务控制: $SERVICE_STOP / $SERVICE_START"
echo "=========================================="

# 获取设备架构
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        PLATFORM="amd64"
        ;;
    aarch64)
        PLATFORM="arm64"
        ;;
    armv7l)
        PLATFORM="armv7"
        ;;
    mips|mipsle)
        PLATFORM="mipsle-softfloat"
        ;;
    *)
        echo "不支持的架构: $ARCH"
        exit 1
        ;;
esac
echo "检测到架构: $ARCH -> $PLATFORM"

# ==================== 检测 CPU 指令集级别（仅 x86_64） ====================
detect_cpu_level() {
    if [ "$PLATFORM" != "amd64" ]; then
        echo "none"
        return
    fi
    
    flags=$(cat /proc/cpuinfo 2>/dev/null | grep -m1 flags | cut -d: -f2-)
    
    if echo "$flags" | grep -q "avx2" && \
       echo "$flags" | grep -q "bmi2" && \
       echo "$flags" | grep -q "fma" && \
       echo "$flags" | grep -q "movbe"; then
        echo "v3"
        return
    fi
    
    if echo "$flags" | grep -q "sse4_2" && \
       echo "$flags" | grep -q "sse4_1" && \
       echo "$flags" | grep -q "ssse3"; then
        echo "v2"
        return
    fi
    
    echo "v1"
}

CPU_LEVEL=$(detect_cpu_level)
[ "$PLATFORM" = "amd64" ] && echo "本机 CPU 最高支持级别: $CPU_LEVEL"

if [ -n "$GITHUB_TOKEN" ]; then
    AUTH_HEADER="Authorization: Bearer $GITHUB_TOKEN"
    echo "使用 GitHub Token 认证访问 API"
else
    AUTH_HEADER=""
    echo "警告: 未设置 GitHub Token，API 请求可能受限流影响"
fi

# ==================== 3. 检测本地版本与目标通道 ====================
if [ ! -f "$LOCAL_BIN_PATH" ]; then
    echo "提示: 本地未找到核心文件 ($LOCAL_BIN_PATH)，判定为全新安装"
    LOCAL_RAW_INFO=""
    LOCAL_VERSION="none"
    CURRENT_CHANNEL="stable"
else
    LOCAL_RAW_INFO=$($LOCAL_BIN_PATH -v 2>/dev/null | head -n1)
    if echo "$LOCAL_RAW_INFO" | grep -qi "alpha"; then
        CURRENT_CHANNEL="alpha"
        LOCAL_VERSION=$(echo "$LOCAL_RAW_INFO" | grep -oE 'alpha-[a-z0-9]+')
    else
        CURRENT_CHANNEL="stable"
        LOCAL_VERSION=$(echo "$LOCAL_RAW_INFO" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
    fi
    [ -z "$LOCAL_VERSION" ] && LOCAL_VERSION="unknown"
fi

echo "本地当前版本: $LOCAL_VERSION (通道: $CURRENT_CHANNEL)"

# 映射目标更新通道
case "$OP_MODE" in
    switch)
        if [ "$CURRENT_CHANNEL" = "alpha" ]; then
            TARGET_CHANNEL="stable"
        else
            TARGET_CHANNEL="alpha"
        fi
        echo ">> 运行模式: 通道反转切换 ($CURRENT_CHANNEL -> $TARGET_CHANNEL)"
        ;;
    alpha)
        TARGET_CHANNEL="alpha"
        echo ">> 运行模式: 目标锁定为 Alpha"
        ;;
    stable)
        TARGET_CHANNEL="stable"
        echo ">> 运行模式: 目标锁定为 Release (Stable)"
        ;;
    default)
        TARGET_CHANNEL="$CURRENT_CHANNEL"
        echo ">> 运行模式: 默认跟随本地通道 ($TARGET_CHANNEL)"
        ;;
esac

# ==================== 4. 获取远端 Release 信息 ====================
mkdir -p "$TMP_DIR"
API_JSON_FILE="$TMP_DIR/release_info.json"

if [ "$TARGET_CHANNEL" = "alpha" ]; then
    echo "正在获取 Alpha 预发布版本信息..."
    API_URL="https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/tags/Prerelease-Alpha"
else
    echo "正在获取最新稳定版 Release 信息..."
    API_URL="https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/latest"
fi

if [ -n "$AUTH_HEADER" ]; then
    curl -s -H "$AUTH_HEADER" "$API_URL" > "$API_JSON_FILE"
else
    curl -s "$API_URL" > "$API_JSON_FILE"
fi

if [ ! -s "$API_JSON_FILE" ] || grep -q '"message": "Not Found"' "$API_JSON_FILE"; then
    echo "错误: 无法从 GitHub API 获取发布信息"
    rm -rf "$TMP_DIR"
    exit 1
fi

DOWNLOAD_SUCCESS=0
DOWNLOADED_LEVEL=""
TARGET_FILE=""

# ==================== 5. 匹配并下载资源 ====================
if [ "$PLATFORM" = "amd64" ]; then
    case "$CPU_LEVEL" in
        v3) LEVEL_LIST="v3 v2 v1" ;;
        v2) LEVEL_LIST="v2 v1" ;;
        *)  LEVEL_LIST="v1" ;;
    esac
else
    LEVEL_LIST="generic"
fi

for level in $LEVEL_LIST; do
    if [ "$TARGET_CHANNEL" = "alpha" ]; then
        if [ "$level" = "generic" ]; then
            SEARCH_PATTERN="mihomo-linux-$PLATFORM-alpha-[a-z0-9]+\.gz"
        else
            SEARCH_PATTERN="mihomo-linux-$PLATFORM-$level-alpha-[a-z0-9]+\.gz"
        fi
    else
        if [ "$level" = "generic" ]; then
            SEARCH_PATTERN="mihomo-linux-$PLATFORM-v[0-9]+\.[0-9]+\.[0-9]+\.gz"
        else
            SEARCH_PATTERN="mihomo-linux-$PLATFORM-$level-v[0-9]+\.[0-9]+\.[0-9]+\.gz"
        fi
    fi

    MATCHED_ASSET=$(grep -oE '"browser_download_url": "[^"]*' "$API_JSON_FILE" | cut -d'"' -f4 | grep -E "$SEARCH_PATTERN" | head -n1)

    if [ -n "$MATCHED_ASSET" ]; then
        FILE_NAME=$(basename "$MATCHED_ASSET")
        echo "匹配到目标资源: $FILE_NAME"

        if [ "$TARGET_CHANNEL" = "alpha" ]; then
            REMOTE_VERSION=$(echo "$FILE_NAME" | grep -oE 'alpha-[a-z0-9]+')
        else
            REMOTE_VERSION=$(echo "$FILE_NAME" | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
        fi

        echo "远端最新版本: $REMOTE_VERSION"

        # 未切换通道且版本一致跳过
        if [ "$CURRENT_CHANNEL" = "$TARGET_CHANNEL" ] && [ "$LOCAL_VERSION" = "$REMOTE_VERSION" ]; then
            echo "本地已是最新版本 ($LOCAL_VERSION)，无需重复更新。"
            rm -rf "$TMP_DIR"
            exit 0
        fi

        echo "开始下载 $FILE_NAME..."
        if curl -L --fail --progress-bar -o "$TMP_DIR/$FILE_NAME" "$MATCHED_ASSET"; then
            DOWNLOAD_SUCCESS=1
            DOWNLOADED_LEVEL="$level"
            TARGET_FILE="$FILE_NAME"
            break
        else
            echo "下载失败，尝试下一兼容级别..."
        fi
    fi
done

if [ $DOWNLOAD_SUCCESS -eq 0 ]; then
    echo "错误: 未找到与当前系统兼容的构建包"
    rm -rf "$TMP_DIR"
    exit 1
fi

# ==================== 6. 解压与校验 ====================
gunzip -f "$TMP_DIR/$TARGET_FILE"
UNPACKED_NAME="${TARGET_FILE%.gz}"

if [ ! -f "$TMP_DIR/$UNPACKED_NAME" ]; then
    echo "错误: 解压未生成目标文件"
    rm -rf "$TMP_DIR"
    exit 1
fi

mv "$TMP_DIR/$UNPACKED_NAME" "$TMP_DIR/mihomo"
chmod +x "$TMP_DIR/mihomo"

if ! "$TMP_DIR/mihomo" -v >/dev/null 2>&1; then
    echo "错误: 下载的核心二进制不可执行或指令集不兼容"
    rm -rf "$TMP_DIR"
    exit 1
fi
echo "校验通过: 新核心可正常运行"

# ==================== 7. 备份与替换核心 ====================
mkdir -p "$(dirname "$LOCAL_BIN_PATH")"

if [ -f "$LOCAL_BIN_PATH" ]; then
    BACKUP_FILE="$LOCAL_BIN_PATH.bak.$(date +%Y%m%d_%H%M%S)"
    cp "$LOCAL_BIN_PATH" "$BACKUP_FILE"
    echo "已生成备份: $BACKUP_FILE"
fi

if [ -n "$SERVICE_STOP" ]; then
    echo "正在停止服务 ($SERVICE_STOP)..."
    $SERVICE_STOP >/dev/null 2>&1
fi

cp "$TMP_DIR/mihomo" "$LOCAL_BIN_PATH"
if [ $? -ne 0 ]; then
    echo "错误: 核心覆盖失败，正在尝试回滚..."
    [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ] && cp "$BACKUP_FILE" "$LOCAL_BIN_PATH"
    [ -n "$SERVICE_START" ] && $SERVICE_START >/dev/null 2>&1
    rm -rf "$TMP_DIR"
    exit 1
fi
chmod +x "$LOCAL_BIN_PATH"

if [ -n "$SERVICE_START" ]; then
    echo "正在启动服务 ($SERVICE_START)..."
    $SERVICE_START >/dev/null 2>&1
fi

rm -rf "$TMP_DIR"

# ==================== 8. 清理历史备份 ====================
if [ -n "$BACKUP_FILE" ]; then
    BACKUP_LIST=$(ls -t "$LOCAL_BIN_PATH.bak."* 2>/dev/null)
    if [ -n "$BACKUP_LIST" ]; then
        OLD_BACKUPS=$(echo "$BACKUP_LIST" | tail -n +$((KEEP_BACKUPS + 1)))
        if [ -n "$OLD_BACKUPS" ]; then
            echo "清理历史旧备份..."
            echo "$OLD_BACKUPS" | while read -r file; do
                rm -f "$file"
                echo "  已删除: $file"
            done
        fi
    fi
fi

NEW_VERSION=$($LOCAL_BIN_PATH -v 2>/dev/null | head -n1)
echo "=========================================="
echo "执行完成！"
echo "部署环境: $ENV_TYPE"
echo "核心路径: $LOCAL_BIN_PATH"
echo "原通道版本: $CURRENT_CHANNEL ($LOCAL_VERSION)"
echo "当前核心信息: $NEW_VERSION"
echo "采用指令集: $DOWNLOADED_LEVEL"
echo "=========================================="