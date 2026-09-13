import os
import re
import ipaddress
import logging
from pathlib import Path
from functools import wraps
import yaml
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from github import Github, Auth

env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip().strip("'\"“”")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip().strip("'\"“”")
ALLOWED_USER_ID_STR = os.getenv("ALLOWED_USER_ID", "0").strip().strip("'\"“”")
ALLOWED_USER_ID = int(ALLOWED_USER_ID_STR) if ALLOWED_USER_ID_STR.isdigit() else 0

REPO_NAME = os.getenv("GITHUB_REPO", "").strip().strip("'\"“”")
RULES_DIR = os.getenv("RULES_DIR", "Rules").strip().strip("'\"“”").strip("/")
TIMEOUT_SECONDS = 60

raw_rule_files = os.getenv("RULE_FILES", "").strip().strip("'\"“”")
if not raw_rule_files:
    raw_rule_files = "直连:Giveup_Direct.yaml, 代理:Giveup_Proxy.yaml"

FILES_CONFIG = {}
for item in raw_rule_files.split(","):
    if ":" in item:
        alias, fname = item.split(":", 1)
        FILES_CONFIG[fname.strip()] = alias.strip()
    elif item.strip():
        FILES_CONFIG[item.strip()] = item.strip()

FILE_KEY_TO_NAME = {}
FILE_NAME_TO_KEY = {}
for idx, fname in enumerate(FILES_CONFIG.keys()):
    key = f"f_{idx}"
    FILE_KEY_TO_NAME[key] = fname
    FILE_NAME_TO_KEY[fname] = key

if not GITHUB_TOKEN or not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ 未检测到 GITHUB_TOKEN 或 TG_BOT_TOKEN，请检查 .env 文件！")

if not REPO_NAME:
    raise ValueError("❌ 未检测到 GITHUB_REPO，请在 .env 文件中配置目标仓库！")

auth = Auth.Token(GITHUB_TOKEN)
gh = Github(auth=auth)
repo = gh.get_repo(REPO_NAME)


def get_file_display_name(fname: str) -> str:
    alias = FILES_CONFIG.get(fname, fname)
    return f"{alias} ({fname})"


def auth_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ALLOWED_USER_ID:
            if update.callback_query:
                await update.callback_query.answer("⛔ 无权操作", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ 无权操作此机器人。")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def reset_user_timer(user_id: int, chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE):
    cancel_user_timer(user_id, context)
    job_name = f"timeout_{user_id}"
    context.job_queue.run_once(
        timeout_handler,
        when=TIMEOUT_SECONDS,
        chat_id=chat_id,
        user_id=user_id,
        data={"message_id": message_id},
        name=job_name,
    )


def cancel_user_timer(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    job_name = f"timeout_{user_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()


async def timeout_handler(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_data = context.application.user_data.get(job.user_id, {})
    message_id = job.data.get("message_id")
    user_data.clear()

    if message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=job.chat_id,
                message_id=message_id,
                text="⌛ *操作超时，未完成输入，已自动取消。*",
                reply_markup=None,
                parse_mode="Markdown",
            )
        except Exception:
            pass


def clean_input(raw_text: str) -> str:
    text = re.sub(r'#.*$', '', raw_text).strip()
    text = re.sub(r'^[#\-\s]+', '', text).strip()
    text = text.strip("'\"“”")
    if '/' in text and not is_ip_or_cidr(text)[0]:
        text = re.sub(r'^https?://', '', text).split('/')[0]
    return text


def is_ip_or_cidr(text: str):
    try:
        net = ipaddress.ip_network(text, strict=False)
        rule_type = "IP-CIDR6" if net.version == 6 else "IP-CIDR"
        return True, str(net), rule_type
    except ValueError:
        pass

    try:
        ip = ipaddress.ip_address(text)
        if ip.version == 6:
            return True, f"{ip}/128", "IP-CIDR6"
        else:
            return True, f"{ip}/32", "IP-CIDR"
    except ValueError:
        pass

    return False, None, None


def get_full_rule_path(filename: str) -> str:
    return f"{RULES_DIR}/{filename}" if RULES_DIR else filename


def parse_raw_rule_lines(text: str) -> list[str]:
    """
    按行解析出带注释的原始规则条目，保证形如:
    - 'DOMAIN-SUFFIX,google.com' # 谷歌
    解析为: 'DOMAIN-SUFFIX,google.com' # 谷歌
    """
    lines = text.splitlines()
    entries = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-"):
            val = stripped.lstrip("-").strip()
            if val:
                entries.append(val)
    return entries


def fetch_rule_file(filename: str):
    file_path = get_full_rule_path(filename)
    file_content = repo.get_contents(file_path)
    decoded_text = file_content.decoded_content.decode("utf-8")
    payload = parse_raw_rule_lines(decoded_text)
    return file_content, payload


def commit_rule_file(file_content, payload_list: list, commit_msg: str):
    """
    序列化时确保注释紧随引号之后：
    payload:
      - 'RULE' # 备注
    """
    if not payload_list:
        updated_text = "payload:\n"
    else:
        lines = ["payload:"]
        for item in payload_list:
            item = item.strip()
            if "#" in item:
                rule_part, comment_part = item.split("#", 1)
                clean_r = rule_part.strip().strip("'\"")
                clean_c = comment_part.strip()
                lines.append(f"  - '{clean_r}' # {clean_c}")
            else:
                clean_r = item.strip().strip("'\"")
                lines.append(f"  - '{clean_r}'")
        updated_text = "\n".join(lines) + "\n"

    repo.update_file(
        path=file_content.path,
        message=commit_msg,
        content=updated_text,
        sha=file_content.sha,
    )


def extract_pure_rule(entry: str) -> str:
    """提取纯规则主体用于比对和检索"""
    rule_part = entry.split("#")[0]
    return rule_part.strip().strip("'\"")


def search_rule_in_all_files(keyword: str):
    results = []
    for fkey, fname in FILE_KEY_TO_NAME.items():
        try:
            _, payload = fetch_rule_file(fname)
            for rule_entry in payload:
                pure_r = extract_pure_rule(rule_entry)
                if keyword in pure_r:
                    results.append({
                        "file_key": fkey,
                        "filename": fname,
                        "rule": rule_entry,
                        "pure_rule": pure_r,
                    })
        except Exception as e:
            logging.error(f"检索文件 {fname} 失败: {e}")
    return results


def get_start_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("➕ 添加规则", callback_data="start_guide_add"),
            InlineKeyboardButton("➖ 删除规则", callback_data="start_guide_del"),
        ],
        [
            InlineKeyboardButton("📄 查看规则文件", callback_data="start_guide_view"),
            InlineKeyboardButton("📖 使用教程", callback_data="start_guide_help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_file_selection_keyboard(action_prefix: str, back_action: str):
    buttons = []
    for fkey, fname in FILE_KEY_TO_NAME.items():
        alias = FILES_CONFIG.get(fname, fname)
        buttons.append([InlineKeyboardButton(f"📁 {alias} ({fname})", callback_data=f"{action_prefix}_{fkey}")])
    buttons.append([InlineKeyboardButton("⬅️ 返回主面板", callback_data=back_action)])
    return InlineKeyboardMarkup(buttons)


def get_help_text() -> str:
    dir_display = f"{RULES_DIR}/" if RULES_DIR else "仓库根目录"
    file_list_str = "\n".join([f"  • `{alias}`: `{fname}`" for fname, alias in FILES_CONFIG.items()])
    return (
        "📖 *Clash 规则管理 Bot 使用教程*\n\n"
        "⚡ *操作说明：*\n"
        "• 任何时候直接发送 **域名**、**IPv4** 或 **IPv6 (含 CIDR)** 即可。\n"
        "• 发送后，Bot 会自动检索所有规则文件查重。\n\n"
        "🔍 *全自动检索机制：*\n"
        "1. **若已存在**：自动指出所在规则文件，并弹出【🗑 删除规则】（含二次确认）。\n"
        "2. **若不存在**：选择写入文件与规则格式后，**系统会提示你发送一段文本作为用途备注**。\n"
        "   - 注释自动添加在单引号外侧：`- 'RULE' # 备注`。\n"
        "   - IPv4 自动匹配 `IP-CIDR`，IPv6 自动匹配 `IP-CIDR6`。\n"
        "   - 超时或未输入备注则不会写入任何规则。\n\n"
        "📁 *当前已挂载文件*：\n"
        f"• 规则目录：`{dir_display}`\n"
        f"{file_list_str}\n\n"
        "💡 *提示*：主面板与帮助为常驻展示，仅在交互操作环节设有 60 秒保护超时。"
    )


@auth_required
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_user_timer(update.effective_user.id, context)
    context.user_data.clear()

    dir_display = f"{RULES_DIR}/" if RULES_DIR else "仓库根目录"
    file_list_str = "\n".join([f"  - {alias}: `{fname}`" for fname, alias in FILES_CONFIG.items()])
    welcome_text = (
        f"🛠 *Clash 规则管理面板*\n\n"
        f"• 目标仓库：`{REPO_NAME}`\n"
        f"• 规则目录：`{dir_display}`\n"
        f"• 管理文件清单（自适应 {len(FILES_CONFIG)} 份）：\n"
        f"{file_list_str}\n\n"
        f"💡 *你可以直接发送域名或 IP*（例如 `google.com`、`1.1.1.1` 或 `2606:4700::1`），也可以通过下方按钮进行操作："
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )


@auth_required
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_user_timer(update.effective_user.id, context)
    context.user_data.clear()
    back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回主面板", callback_data="act_cancel")]])
    await update.message.reply_text(get_help_text(), reply_markup=back_kb, parse_mode="Markdown")


@auth_required
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_user_timer(update.effective_user.id, context)
    context.user_data.clear()
    await update.message.reply_text("❌ 当前操作已取消。可直接发送新内容开始操作。")


@auth_required
async def view_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancel_user_timer(update.effective_user.id, context)
    context.user_data.clear()
    await update.message.reply_text(
        "📂 *请选择需要查看的规则文件：*",
        reply_markup=get_file_selection_keyboard("do_view", "act_cancel"),
        parse_mode="Markdown",
    )


@auth_required
async def handle_incoming_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw_text = update.message.text.strip()

    # --- 分支 A：用户输入备注 ---
    if context.user_data.get("awaiting_comment"):
        cancel_user_timer(user_id, context)
        final_rule_base = context.user_data.get("pending_rule")
        filename = context.user_data.get("target_file")

        clean_comment = raw_text.replace("\n", " ").replace("#", "").strip()
        if not clean_comment:
            clean_comment = "未备注"

        # 构造带有注释标记的条目：'RULE' # 备注
        final_entry = f"'{final_rule_base}' # {clean_comment}"

        status_tip = await update.message.reply_text(
            f"⏳ 正在写入 `{final_entry}` 到 `{get_file_display_name(filename)}` ...",
            parse_mode="Markdown",
        )

        try:
            file_content, payload = fetch_rule_file(filename)
            payload.append(final_entry)
            commit_rule_file(file_content, payload, f"Bot: Add {final_entry} to {filename}")

            success_text = (
                f"✅ *添加成功！*\n\n"
                f"• 文件：`{get_file_display_name(filename)}`\n"
                f"• 规则：`{final_rule_base}`\n"
                f"• 备注：`{clean_comment}`\n"
                f"• 当前总规则数：`{len(payload)}` 条"
            )
            await status_tip.edit_text(success_text, parse_mode="Markdown")
        except Exception as e:
            await status_tip.edit_text(f"❌ 写入失败：`{str(e)}`", parse_mode="Markdown")

        context.user_data.clear()
        return

    # --- 分支 B：常规流程（发送域名或 IP） ---
    target_val = clean_input(raw_text)
    if not target_val:
        await update.message.reply_text("⚠️ 未识别到有效内容，请重新发送。")
        return

    is_ip, cidr_str, ip_rule_type = is_ip_or_cidr(target_val)
    search_keyword = cidr_str if is_ip else target_val

    matches = search_rule_in_all_files(search_keyword)

    context.user_data["raw_input"] = target_val
    context.user_data["is_ip"] = is_ip
    context.user_data["ip_cidr"] = cidr_str
    context.user_data["ip_rule_type"] = ip_rule_type
    context.user_data["matches"] = matches

    if matches:
        details = [f"  • `{m['rule']}` (位于 *{get_file_display_name(m['filename'])}*)" for m in matches]
        detail_text = "\n".join(details)
        msg_text = (
            f"⚠️ *检测到该规则已经存在！*\n\n"
            f"📌 *匹配到的完整规则：*\n{detail_text}\n\n"
            f"请在 {TIMEOUT_SECONDS} 秒内选择操作："
        )
        kb = [
            [InlineKeyboardButton("🗑 删除规则", callback_data="act_del_from_exist")],
            [InlineKeyboardButton("❌ 取消操作", callback_data="act_cancel")],
        ]
        sent_msg = await update.message.reply_text(
            msg_text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    else:
        type_desc = f"{ip_rule_type} (`{cidr_str}`)" if is_ip else f"域名/关键词 (`{target_val}`)"
        msg_text = (
            f"✅ *全部文件中均未查到该规则*\n\n"
            f"🔍 *识别内容*：{type_desc}\n\n"
            f"请在 {TIMEOUT_SECONDS} 秒内选择要写入的目标文件："
        )
        kb = get_file_selection_keyboard("add_to", "act_cancel")
        sent_msg = await update.message.reply_text(
            msg_text,
            reply_markup=kb,
            parse_mode="Markdown"
        )

    context.user_data["panel_msg_id"] = sent_msg.message_id
    reset_user_timer(user_id, update.effective_chat.id, sent_msg.message_id, context)


@auth_required
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    msg_id = query.message.message_id
    context.user_data["panel_msg_id"] = msg_id

    # 1. 取消操作
    if data == "act_cancel":
        cancel_user_timer(user_id, context)
        context.user_data.clear()
        dir_display = f"{RULES_DIR}/" if RULES_DIR else "仓库根目录"
        file_list_str = "\n".join([f"  - {alias}: `{fname}`" for fname, alias in FILES_CONFIG.items()])
        welcome_text = (
            f"🛠 *Clash 规则管理面板*\n\n"
            f"• 目标仓库：`{REPO_NAME}`\n"
            f"• 规则目录：`{dir_display}`\n"
            f"• 管理文件清单（自适应 {len(FILES_CONFIG)} 份）：\n"
            f"{file_list_str}\n\n"
            f"💡 *你可以直接发送域名或 IP*，也可以通过下方按钮操作："
        )
        await query.edit_message_text(
            welcome_text,
            reply_markup=get_start_keyboard(),
            parse_mode="Markdown"
        )
        return

    # 2. 引导与纯展示菜单
    if data == "start_guide_add":
        cancel_user_timer(user_id, context)
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回主面板", callback_data="act_cancel")]])
        await query.edit_message_text(
            "✏️ *添加规则流程*\n\n"
            "请直接发送你需要添加的 **域名**、**IPv4** 或 **IPv6**（例如 `google.com`、`1.1.1.1` 或 `2606:4700::1`）。\n\n"
            "系统会自动检索是否存在；选择格式后会提示你输入用途备注。",
            reply_markup=cancel_kb,
            parse_mode="Markdown",
        )
        return

    if data == "start_guide_del":
        cancel_user_timer(user_id, context)
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回主面板", callback_data="act_cancel")]])
        await query.edit_message_text(
            "🗑 *删除规则流程*\n\n"
            "请直接发送需要删除的 **域名、IP 或规则关键词**。\n\n"
            "系统会自动检索其所在位置并弹出确认删除按钮。",
            reply_markup=cancel_kb,
            parse_mode="Markdown",
        )
        return

    if data == "start_guide_view":
        cancel_user_timer(user_id, context)
        await query.edit_message_text(
            "📂 *请选择需要查看的规则文件：*",
            reply_markup=get_file_selection_keyboard("do_view", "act_cancel"),
            parse_mode="Markdown",
        )
        return

    if data == "start_guide_help":
        cancel_user_timer(user_id, context)
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回主面板", callback_data="act_cancel")]])
        await query.edit_message_text(get_help_text(), reply_markup=back_kb, parse_mode="Markdown")
        return

    # 3. 删除操作
    if data == "act_del_from_exist":
        reset_user_timer(user_id, chat_id, msg_id, context)
        matches = context.user_data.get("matches", [])
        if not matches:
            await query.edit_message_text("⚠️ 会话已过期，请重新发送内容。")
            return

        if len(matches) == 1:
            m = matches[0]
            confirm_kb = [
                [InlineKeyboardButton("⚠️ 确认删除", callback_data="confirm_del_single_0")],
                [InlineKeyboardButton("❌ 取消", callback_data="act_cancel")],
            ]
            await query.edit_message_text(
                f"📁 所在文件：`{get_file_display_name(m['filename'])}`\n"
                f"📌 目标规则：`{m['rule']}`\n\n"
                f"⚠️ *请二次确认：是否立刻彻底删除此规则？*",
                reply_markup=InlineKeyboardMarkup(confirm_kb),
                parse_mode="Markdown",
            )
            return

        btns = []
        for idx, m in enumerate(matches[:6]):
            alias = FILES_CONFIG.get(m["filename"], m["filename"])
            btns.append([InlineKeyboardButton(f"[{alias}] {m['rule']}", callback_data=f"select_del_idx_{idx}")])
        btns.append([InlineKeyboardButton("❌ 取消", callback_data="act_cancel")])
        await query.edit_message_text(
            "⚠️ 检索到多条记录，请点击选择要删除的具体规则：",
            reply_markup=InlineKeyboardMarkup(btns),
        )
        return

    if data.startswith("select_del_idx_"):
        reset_user_timer(user_id, chat_id, msg_id, context)
        idx = int(data.replace("select_del_idx_", ""))
        matches = context.user_data.get("matches", [])
        if idx >= len(matches):
            await query.edit_message_text("⚠️ 会话已失效，请重新发送。")
            return

        target = matches[idx]
        confirm_kb = [
            [InlineKeyboardButton("⚠️ 确认删除", callback_data=f"confirm_del_single_{idx}")],
            [InlineKeyboardButton("⬅️ 返回", callback_data="act_del_from_exist")],
        ]
        await query.edit_message_text(
            f"📁 目标文件：`{get_file_display_name(target['filename'])}`\n"
            f"📌 准备删除：`{target['rule']}`\n\n"
            f"⚠️ *请二次确认：是否立刻彻底删除此规则？*",
            reply_markup=InlineKeyboardMarkup(confirm_kb),
            parse_mode="Markdown",
        )
        return

    if data.startswith("confirm_del_single_"):
        cancel_user_timer(user_id, context)
        idx = int(data.replace("confirm_del_single_", ""))
        matches = context.user_data.get("matches", [])
        if idx >= len(matches):
            await query.edit_message_text("⚠️ 会话已失效，请重新发送内容。")
            return

        target_item = matches[idx]
        filename = target_item["filename"]
        target_rule = target_item["rule"]

        await query.edit_message_text(f"⏳ 正在从 `{filename}` 移除规则...", parse_mode="Markdown")
        try:
            file_content, payload = fetch_rule_file(filename)
            # 按原始行或纯规则部分精确比对
            matched_index = None
            for i, p in enumerate(payload):
                if p == target_rule or extract_pure_rule(p) == extract_pure_rule(target_rule):
                    matched_index = i
                    break

            if matched_index is not None:
                removed_item = payload.pop(matched_index)
                commit_rule_file(file_content, payload, f"Bot: Remove {removed_item} from {filename}")
                await query.edit_message_text(
                    f"🗑 *二次确认通过，删除成功！*\n\n"
                    f"• 文件：`{get_file_display_name(filename)}`\n"
                    f"• 已删除规则：`{removed_item}`\n"
                    f"• 剩余总规则数：`{len(payload)}` 条",
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(f"⚠️ 文件中已无规则 `{target_rule}`。", parse_mode="Markdown")
            context.user_data.clear()
        except Exception as e:
            await query.edit_message_text(f"❌ 删除失败：`{str(e)}`", parse_mode="Markdown")
        return

    # 4. 选择写入文件
    if data.startswith("add_to_"):
        target_fkey = data.replace("add_to_", "")
        filename = FILE_KEY_TO_NAME.get(target_fkey)
        if not filename:
            await query.edit_message_text("⚠️ 未找到对应文件，请重新发送内容。")
            return

        context.user_data["target_file"] = filename
        is_ip = context.user_data.get("is_ip")

        if is_ip:
            reset_user_timer(user_id, chat_id, msg_id, context)
            rule_prefix = context.user_data.get("ip_rule_type", "IP-CIDR")
            cidr_rule = f"{rule_prefix},{context.user_data.get('ip_cidr')}"
            context.user_data["pending_rule"] = cidr_rule
            context.user_data["awaiting_comment"] = True

            cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消操作", callback_data="act_cancel")]])
            await query.edit_message_text(
                f"✍️ *请输入规则备注/用途*\n\n"
                f"• 目标文件：`{get_file_display_name(filename)}`\n"
                f"• 待加规则：`'{cidr_rule}'`\n\n"
                f"⚠️ *请在 {TIMEOUT_SECONDS} 秒内直接回复一段文本作为该网址/IP的用途备注*（未输入则不会加入规则库）：",
                reply_markup=cancel_kb,
                parse_mode="Markdown",
            )
            return

        reset_user_timer(user_id, chat_id, msg_id, context)
        domain = context.user_data.get("raw_input")
        domain_kb = [
            [InlineKeyboardButton(f"DOMAIN-SUFFIX,{domain}", callback_data="final_add_SUFFIX")],
            [InlineKeyboardButton(f"DOMAIN-KEYWORD,{domain}", callback_data="final_add_KEYWORD")],
            [InlineKeyboardButton(f"DOMAIN,{domain}", callback_data="final_add_EXACT")],
            [InlineKeyboardButton("❌ 取消操作", callback_data="act_cancel")],
        ]
        await query.edit_message_text(
            f"🎯 目标文件：`{get_file_display_name(filename)}`\n"
            f"域名内容：`{domain}`\n\n"
            f"👇 *请点击按钮选择需要的规则形式：*",
            reply_markup=InlineKeyboardMarkup(domain_kb),
            parse_mode="Markdown",
        )
        return

    # 5. 格式确认后要求输入备注
    if data.startswith("final_add_"):
        reset_user_timer(user_id, chat_id, msg_id, context)
        rule_type = data.replace("final_add_", "")
        domain = context.user_data.get("raw_input")
        filename = context.user_data.get("target_file")

        type_map = {
            "SUFFIX": "DOMAIN-SUFFIX",
            "KEYWORD": "DOMAIN-KEYWORD",
            "EXACT": "DOMAIN",
        }
        final_rule_base = f"{type_map[rule_type]},{domain}"

        context.user_data["pending_rule"] = final_rule_base
        context.user_data["awaiting_comment"] = True

        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ 取消操作", callback_data="act_cancel")]])
        await query.edit_message_text(
            f"✍️ *请输入规则备注/用途*\n\n"
            f"• 目标文件：`{get_file_display_name(filename)}`\n"
            f"• 待加规则：`'{final_rule_base}'`\n\n"
            f"⚠️ *请在 {TIMEOUT_SECONDS} 秒内直接回复一段文本作为该网址的用途备注*（未输入则不会加入规则库）：",
            reply_markup=cancel_kb,
            parse_mode="Markdown",
        )
        return

    # 6. 单独查看指定文件
    if data.startswith("do_view_"):
        cancel_user_timer(user_id, context)
        target_fkey = data.replace("do_view_", "")
        filename = FILE_KEY_TO_NAME.get(target_fkey)
        if not filename:
            await query.edit_message_text("⚠️ 未找到对应文件。")
            return

        await query.edit_message_text(f"⏳ 正在拉取 `{filename}` ...", parse_mode="Markdown")
        try:
            _, payload = fetch_rule_file(filename)
            total = len(payload)
            preview = "\n".join([f"  - `{item}`" for item in payload[-8:]]) if total > 0 else "  (当前无规则)"

            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回", callback_data="start_guide_view")]])
            res_text = (
                f"📄 *文件：* `{get_file_display_name(filename)}`\n"
                f"📊 *规则总数：* `{total}` 条\n\n"
                f"📌 *最新规则预览 (最多8条)：*\n{preview}"
            )
            await query.edit_message_text(res_text, reply_markup=back_kb, parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ 读取失败：`{str(e)}`", parse_mode="Markdown")
        return


async def register_bot_commands(application: Application):
    commands = [
        BotCommand("start", "呼出规则管理面板与操作按钮"),
        BotCommand("menu", "打开快捷功能菜单"),
        BotCommand("view", "查看各规则文件预览"),
        BotCommand("help", "查看详细使用教程与说明"),
        BotCommand("cancel", "取消当前正在进行的操作"),
    ]
    await application.bot.set_my_commands(commands)
    logging.info("✅ Telegram 官方快捷指令列表注册成功！")


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(register_bot_commands).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("menu", start_cmd))
    app.add_handler(CommandHandler("view", view_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_text))

    print(f"自适应 Clash 规则管理 Bot 已启动（当前共挂载 {len(FILES_CONFIG)} 份文件）...")
    app.run_polling()


if __name__ == "__main__":
    main()