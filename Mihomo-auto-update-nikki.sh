#!/bin/sh

# ==================== 配置区域 ====================
LOCAL_BIN_PATH="/usr/bin/mihomo"

REPO_OWNER="MetaCubeX"
REPO_NAME="mihomo"
TMP_DIR="/tmp/mihomo_update"

# 保留备份文件数量
KEEP_BACKUPS=3

# GitHub Token 配置
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
# ================================================

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

# ==================== 检测本机 CPU 支持的指令集级别（仅 x86_64） ====================
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

if [ "$PLATFORM" = "amd64" ]; then
    echo "本机 CPU 最高支持级别: $CPU_LEVEL"
fi

if [ -n "$GITHUB_TOKEN" ]; then
    echo "使用 GitHub Token 认证访问 API"
else
    echo "警告: 未设置 GitHub Token，API 请求可能受限流影响"
fi

# 1. 获取本地版本
if [ ! -f "$LOCAL_BIN_PATH" ]; then
    echo "错误: 本地 mihomo 二进制文件未找到: $LOCAL_BIN_PATH"
    exit 1
fi

LOCAL_VERSION=$($LOCAL_BIN_PATH -v 2>/dev/null | head -n1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+')
if [ -z "$LOCAL_VERSION" ]; then
    echo "错误: 无法获取本地版本信息"
    echo "当前输出: $($LOCAL_BIN_PATH -v 2>/dev/null | head -n1)"
    exit 1
fi
echo "本地 mihomo 版本: $LOCAL_VERSION"

# 2. 从 GitHub API 获取最新稳定版
echo "正在从 GitHub API 获取最新稳定版..."
if [ -n "$GITHUB_TOKEN" ]; then
    LATEST_VERSION=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
        "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/latest" \
        | grep -oE '"tag_name": "([^"]+)"' | head -n1 | sed 's/"tag_name": "//' | sed 's/"//')
else
    LATEST_VERSION=$(curl -s \
        "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/latest" \
        | grep -oE '"tag_name": "([^"]+)"' | head -n1 | sed 's/"tag_name": "//' | sed 's/"//')
fi

if [ -z "$LATEST_VERSION" ]; then
    echo "错误: 无法从 GitHub API 获取最新版本"
    echo "尝试使用备用方案（从 releases 列表获取）..."
    if [ -n "$GITHUB_TOKEN" ]; then
        LATEST_VERSION=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
            "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases?per_page=5" \
            | grep -oE '"tag_name": "v[0-9]+\.[0-9]+\.[0-9]+"' | head -n1 | sed 's/"tag_name": "//' | sed 's/"//')
    else
        LATEST_VERSION=$(curl -s \
            "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases?per_page=5" \
            | grep -oE '"tag_name": "v[0-9]+\.[0-9]+\.[0-9]+"' | head -n1 | sed 's/"tag_name": "//' | sed 's/"//')
    fi
    if [ -z "$LATEST_VERSION" ]; then
        echo "错误: 所有方案均失败，请检查网络"
        exit 1
    fi
fi
echo "GitHub 最新版本: $LATEST_VERSION"

# 3. 比较版本
if [ "$LOCAL_VERSION" = "$LATEST_VERSION" ]; then
    echo "本地已是最新版本，无需更新。"
    exit 0
fi

echo "发现新版本 $LATEST_VERSION，开始下载更新..."

# ==================== 4. 根据架构下载 ====================
mkdir -p "$TMP_DIR"

DOWNLOAD_SUCCESS=0
DOWNLOADED_LEVEL=""

if [ "$PLATFORM" = "amd64" ]; then
    case "$CPU_LEVEL" in
        v3)
            LEVEL_LIST="v3 v2 v1"
            ;;
        v2)
            LEVEL_LIST="v2 v1"
            ;;
        *)
            LEVEL_LIST="v1"
            ;;
    esac
    
    echo "开始逐级尝试下载（从 $CPU_LEVEL 开始降级）..."
    for level in $LEVEL_LIST; do
        DOWNLOAD_URL="https://github.com/$REPO_OWNER/$REPO_NAME/releases/download/$LATEST_VERSION/mihomo-linux-$PLATFORM-$level-$LATEST_VERSION.gz"
        echo "  尝试: $level 级别"
        
        if curl -L --fail --output /dev/null --silent --head "$DOWNLOAD_URL"; then
            echo "  ✓ 找到 $level 级别版本，开始下载..."
            DOWNLOAD_FILE="mihomo-linux-$PLATFORM-$level-$LATEST_VERSION.gz"
            if curl -L --fail --progress-bar -o "$TMP_DIR/$DOWNLOAD_FILE" "$DOWNLOAD_URL"; then
                DOWNLOAD_SUCCESS=1
                DOWNLOADED_LEVEL="$level"
                echo "  ✓ 下载成功: $level 级别"
                gunzip -f "$TMP_DIR/$DOWNLOAD_FILE"
                EXTRACTED_FILE="mihomo-linux-$PLATFORM-$level-$LATEST_VERSION"
                if [ ! -f "$TMP_DIR/$EXTRACTED_FILE" ]; then
                    echo "错误: 解压失败"
                    rm -rf "$TMP_DIR"
                    exit 1
                fi
                
                # 重命名为 mihomo
                mv "$TMP_DIR/$EXTRACTED_FILE" "$TMP_DIR/mihomo"
                echo "解压完成: $EXTRACTED_FILE -> mihomo"
                break
            else
                echo "  ✗ 下载失败"
            fi
        else
            echo "  ✗ $level 级别不存在"
        fi
    done
    
    if [ $DOWNLOAD_SUCCESS -eq 0 ]; then
        echo ""
        echo "=========================================="
        echo "错误: 所有指令集级别版本均不存在"
        echo "尝试过的级别: ${LEVEL_LIST}"
        echo "Release 版本: $LATEST_VERSION"
        echo "请检查: https://github.com/$REPO_OWNER/$REPO_NAME/releases/tag/$LATEST_VERSION"
        echo "=========================================="
        rm -rf "$TMP_DIR"
        exit 1
    fi
else
    echo "非 x86_64 平台，使用通用版本..."
    DOWNLOAD_URL="https://github.com/$REPO_OWNER/$REPO_NAME/releases/download/$LATEST_VERSION/mihomo-linux-$PLATFORM-$LATEST_VERSION.gz"
    echo "下载地址: $DOWNLOAD_URL"
    
    DOWNLOAD_FILE="mihomo-linux-$PLATFORM-$LATEST_VERSION.gz"
    if ! curl -L --fail --progress-bar -o "$TMP_DIR/$DOWNLOAD_FILE" "$DOWNLOAD_URL"; then
        echo "错误: 通用版本下载失败"
        rm -rf "$TMP_DIR"
        exit 1
    fi
    DOWNLOADED_LEVEL="通用版本"
    echo "通用版本下载成功"
    
    # 解压
    gunzip -f "$TMP_DIR/$DOWNLOAD_FILE"
    EXTRACTED_FILE="mihomo-linux-$PLATFORM-$LATEST_VERSION"
    if [ ! -f "$TMP_DIR/$EXTRACTED_FILE" ]; then
        echo "错误: 解压失败"
        rm -rf "$TMP_DIR"
        exit 1
    fi
    
    # 重命名为 mihomo
    mv "$TMP_DIR/$EXTRACTED_FILE" "$TMP_DIR/mihomo"
    echo "解压完成: $EXTRACTED_FILE -> mihomo"
fi

# 添加执行权限
chmod +x "$TMP_DIR/mihomo"
echo "已添加执行权限"

# 验证下载的文件是否可用
if ! "$TMP_DIR/mihomo" -v >/dev/null 2>&1; then
    echo "错误: 下载的文件不可执行或已损坏"
    rm -rf "$TMP_DIR"
    exit 1
fi
echo "验证通过: 文件可执行"

# 5. 替换二进制文件
echo "准备更新..."

BACKUP_FILE="$LOCAL_BIN_PATH.bak.$(date +%Y%m%d_%H%M%S)"
cp "$LOCAL_BIN_PATH" "$BACKUP_FILE"
if [ $? -ne 0 ]; then
    echo "警告: 备份失败，继续执行..."
else
    echo "备份已保存: $BACKUP_FILE"
fi

echo "停止 nikki 服务..."
/etc/init.d/nikki stop 2>/dev/null

cp "$TMP_DIR/mihomo" "$LOCAL_BIN_PATH"
if [ $? -ne 0 ]; then
    echo "错误: 替换文件失败"
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$LOCAL_BIN_PATH"
        echo "已恢复备份文件"
    fi
    rm -rf "$TMP_DIR"
    exit 1
fi
chmod +x "$LOCAL_BIN_PATH"

echo "启动 nikki 服务..."
/etc/init.d/nikki start 2>/dev/null

rm -rf "$TMP_DIR"

# ==================== 6. 清理旧备份 ====================
if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
    BACKUP_LIST=$(ls -t "$LOCAL_BIN_PATH.bak."* 2>/dev/null)
    
    if [ -n "$BACKUP_LIST" ]; then
        OLD_BACKUPS=$(echo "$BACKUP_LIST" | tail -n +$((KEEP_BACKUPS + 1)))
        
        if [ -n "$OLD_BACKUPS" ]; then
            echo "清理旧备份文件（保留最近 $KEEP_BACKUPS 个）..."
            echo "$OLD_BACKUPS" | while read -r file; do
                rm -f "$file"
                echo "  已删除: $file"
            done
        else
            echo "备份文件数量未超过 $KEEP_BACKUPS 个，无需清理。"
        fi
    fi
fi

# ==================== 显示结果 ====================
NEW_VERSION=$($LOCAL_BIN_PATH -v 2>/dev/null | head -n1)
echo "=========================================="
echo "更新完成！"
echo "旧版本: $LOCAL_VERSION"
echo "新版本: $NEW_VERSION"
if [ "$PLATFORM" = "amd64" ]; then
    echo "本机 CPU 最高支持级别: $CPU_LEVEL"
fi
echo "实际下载版本: $DOWNLOADED_LEVEL"
echo "当前备份: $BACKUP_FILE"
echo "保留备份数: $KEEP_BACKUPS"
echo "=========================================="