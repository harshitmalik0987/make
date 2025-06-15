import json
import logging
import requests
from uuid import uuid4
from functools import wraps
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
)
from telegram.constants import ParseMode

# --- CONFIG LOAD/SAVE ---
def load_config():
    with open('config.json') as f:
        return json.load(f)

def save_config(cfg):
    with open('config.json', 'w') as f:
        json.dump(cfg, f, indent=2)

config = load_config()
BOT_TOKEN = config["BOT_TOKEN"]
PANEL_API_KEY = config["PANEL_API_KEY"]
SERVICE_ID = config["SERVICE_ID"]
PANEL_URL = config["PANEL_URL"]
ADMIN_PASSWORD = config["ADMIN_PASSWORD"]
FORCE_JOIN_CHANNELS = config.get("FORCE_JOIN_CHANNELS", ["@YourForceJoinChannel"])
PAYOUT_CHANNEL = config["PAYOUT_CHANNEL"]

USERS_FILE = "users.json"
CODES_FILE = "codes.json"
BANNED_FILE = "banned.json"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def load_json(file, default):
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

users = load_json(USERS_FILE, {})
codes = load_json(CODES_FILE, {})
banned = set(load_json(BANNED_FILE, []))

def update_users():
    save_json(USERS_FILE, users)

def update_codes():
    save_json(CODES_FILE, codes)

def update_banned():
    save_json(BANNED_FILE, list(banned))

def user_is_banned(user_id):
    return str(user_id) in banned

def admin_required(func):
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if users.get(str(user_id), {}).get("is_admin", False):
            return await func(update, context)
        else:
            await update.message.reply_text("⛔️ Sorry, this section is for admins only!")
    return wrapper

def order_views(link, quantity):
    payload = {
        "key": PANEL_API_KEY,
        "action": "add",
        "service": SERVICE_ID,
        "link": link,
        "quantity": quantity
    }
    try:
        r = requests.post(PANEL_URL, data=payload, timeout=10)
        return r.json()
    except Exception as ex:
        return {"error": str(ex)}

async def check_force_join(user_id, bot):
    for channel in FORCE_JOIN_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status not in ["creator", "administrator", "member"]:
                return False
        except Exception:
            return False
    return True

# --- HANDLERS ---

async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    user_id = str(user.id)
    args = context.args
    referred_by = args[0] if args else None

    if user_is_banned(user_id):
        await update.message.reply_text("🚫 Sorry, you are banned from using this bot. Contact support if you think this is a mistake.")
        return

    if not await check_force_join(user.id, context.bot):
        kb = []
        for channel in FORCE_JOIN_CHANNELS:
            kb.append([InlineKeyboardButton(f"🚀 Join {channel}", url=f"https://t.me/{channel.lstrip('@')}")])
        kb.append([InlineKeyboardButton("✅ Joined All! Tap Here", callback_data="check_join")])
        await update.message.reply_text(
            "🔐 <b>Access Restricted!</b>\n\n"
            "To unlock all features, please join ALL our official channels below.\n"
            + "\n".join([f"• {ch}" for ch in FORCE_JOIN_CHANNELS]) +
            "\n\nOnce done, tap <b>Joined All! Tap Here</b> below 👇",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
        )
        return

    first_time = False
    if user_id not in users:
        users[user_id] = {
            "balance": 500,
            "refs": [],
            "is_admin": False,
            "history": [],
            "referred_by": None
        }
        first_time = True
        if referred_by and referred_by != user_id and referred_by in users:
            users[user_id]["referred_by"] = referred_by
            users[referred_by]["refs"].append(user_id)
            users[referred_by]["balance"] += 250
    update_users()

    kb = [
        ["💰 Balance", "🎁 Withdraw"],
        ["🔗 My Referral", "📊 History"],
        ["🔑 Redeem", "ℹ️ Help"]
    ]
    welcome_text = (
        f"👋 <b>Welcome, {user.first_name}!</b>\n\n"
        "🔥 <b>You're now part of the coolest view exchange bot on Telegram!</b>\n\n"
        "✨ <b>Features:</b>\n"
        "• <b>💸 Earn points</b> by inviting friends\n"
        "• <b>👁️ Get real Telegram views</b> on your posts\n"
        "• <b>🎟️ Redeem special codes</b> for instant rewards\n"
        "• <b>🚀 Fast payouts, instant panel integration</b>\n\n"
        "Hit the menu below and start your journey! 🚀"
    )
    if first_time:
        welcome_text += "\n\n🎉 <b>Sign Up Bonus:</b> You got <b>500 views</b> (500 points) to start!"

    reply_kb = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=reply_kb, parse_mode=ParseMode.HTML)

async def force_join_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    if await check_force_join(user_id, context.bot):
        await query.answer()
        await context.bot.send_message(user_id, "✅ Awesome! You’ve unlocked the bot. Type /start to continue.")
    else:
        await query.answer("❌ You need to join all channels first!", show_alert=True)

async def balance(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_is_banned(user_id):
        return await update.message.reply_text("🚫 Sorry, you are banned from using this bot.")
    bal = users.get(user_id, {}).get("balance", 0)
    await update.message.reply_text(
        f"💰 <b>Your Points:</b> <code>{bal}</code>\n\n"
        "1 Point = 1 View.\n"
        "Earn more points by inviting friends with your referral link, or redeem codes for instant bonuses! 🚀",
        parse_mode=ParseMode.HTML
    )

async def refer(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_is_banned(user_id):
        return await update.message.reply_text("🚫 Sorry, you are banned from using this bot.")
    link = f"https://t.me/{context.bot.username}?start={user_id}"
    refs = users.get(user_id, {}).get("refs", [])
    await update.message.reply_text(
        f"🔗 <b>Your Personal Referral Link:</b>\n"
        f"<code>{link}</code>\n\n"
        f"👤 <b>Referrals:</b> <code>{len(refs)}</code>\n\n"
        "Invite friends & earn <b>250 points</b> (250 views) for each successful referral! 🤑",
        parse_mode=ParseMode.HTML
    )

WITHDRAW_LINK, WITHDRAW_AMOUNT = range(2)

async def withdraw(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_is_banned(user_id):
        return await update.message.reply_text("🚫 Sorry, you are banned from using this bot.")
    await update.message.reply_text(
        "🔗 <b>Send the public Telegram POST link you want to boost (must be from a public channel):</b>",
        parse_mode=ParseMode.HTML
    )
    return WITHDRAW_LINK

async def withdraw_link(update: Update, context: CallbackContext):
    context.user_data["withdraw_link"] = update.message.text.strip()
    await update.message.reply_text(
        "🔢 <b>How many views do you want?</b>\n"
        "<b>1 point = 1 view</b>\n"
        "Enter the number of views you want to order (minimum 10):",
        parse_mode=ParseMode.HTML
    )
    return WITHDRAW_AMOUNT

async def withdraw_amount(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    try:
        amount = int(update.message.text)
    except Exception:
        await update.message.reply_text("❌ Please send a valid number (e.g. 100, 200, 500).")
        return ConversationHandler.END
    points_needed = amount
    balance = users.get(user_id, {}).get("balance", 0)
    if amount < 10:
        await update.message.reply_text("❗️ Minimum is 10 views.")
        return ConversationHandler.END
    if balance < points_needed:
        await update.message.reply_text(
            f"⏳ You need <b>{points_needed}</b> points, but you only have <b>{balance}</b>.\n"
            "Earn more by referring friends or redeeming codes!",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    link = context.user_data.get("withdraw_link")
    resp = order_views(link, amount)
    if "order" in resp and "error" not in resp:
        users[user_id]["balance"] -= points_needed
        users[user_id]["history"].append({"type": "withdraw", "amount": amount, "link": link})
        update_users()
        await update.message.reply_text(
            f"🎉 <b>Success!</b> Your order for <b>{amount} views</b> is being processed!\n"
            f"🆔 Order ID: <code>{resp['order']}</code>\n"
            "You'll get notified when it's done. Thanks for using our bot! 🚀",
            parse_mode=ParseMode.HTML
        )
        if PAYOUT_CHANNEL and PAYOUT_CHANNEL.startswith("@"):
            await context.bot.send_message(
                chat_id=PAYOUT_CHANNEL,
                text=f"💸 <b>User:</b> <a href='tg://user?id={user_id}'>{user_id}</a>\n"
                     f"<b>Withdrew:</b> {amount} views\n"
                     f"<b>Post:</b> <a href='{link}'>Link</a>",
                parse_mode=ParseMode.HTML
            )
    else:
        err = resp.get('error', resp)
        await update.message.reply_text(f"❌ <b>Order failed:</b> {err}", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def history(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_is_banned(user_id):
        return await update.message.reply_text("🚫 Sorry, you are banned from using this bot.")
    hist = users.get(user_id, {}).get("history", [])
    if not hist:
        await update.message.reply_text("📭 <b>Your history is empty!</b> Withdraw views or redeem a code to see your activity here.", parse_mode=ParseMode.HTML)
        return
    msg = "<b>📊 Your Recent Activity:</b>\n\n"
    for item in hist[-10:]:
        if item["type"] == "withdraw":
            msg += f"• <b>Withdraw:</b> {item['amount']} views | <a href='{item['link']}'>View Post</a>\n"
        if item["type"] == "redeem":
            msg += f"• <b>Redeem:</b> {item['amount']} points | Code: <code>{item['code']}</code>\n"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

REDEEM_CODE = range(1)
async def redeem(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_is_banned(user_id):
        return await update.message.reply_text("🚫 Sorry, you are banned from using this bot.")
    await update.message.reply_text("🔑 <b>Enter your redeem code:</b>", parse_mode=ParseMode.HTML)
    return REDEEM_CODE

async def redeem_code(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    code = update.message.text.strip().upper()
    if code in codes and not codes[code].get("used", False):
        amount = codes[code]["amount"]
        users[user_id]["balance"] += amount
        users[user_id]["history"].append({"type": "redeem", "code": code, "amount": amount})
        codes[code]["used"] = True
        codes[code]["used_by"] = user_id
        update_users()
        update_codes()
        await update.message.reply_text(
            f"🎉 <b>Congratulations!</b> You received <b>{amount} points</b>. Enjoy your rewards! 🥳",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ <b>Invalid or already used code.</b>\n"
            "Please check your code and try again.",
            parse_mode=ParseMode.HTML
        )
    return ConversationHandler.END

ADMIN_PASS, ADD_CHANNEL = range(2)
async def admin(update: Update, context: CallbackContext):
    await update.message.reply_text("🔑 <b>Enter admin panel password:</b>", parse_mode=ParseMode.HTML)
    return ADMIN_PASS

async def admin_pass(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    password = update.message.text.strip()
    if password == ADMIN_PASSWORD:
        users[user_id]["is_admin"] = True
        update_users()
        kb = [
            ["/gen_code", "/broadcast"],
            ["/ban", "/unban"],
            ["/add_channel", "/show_channels"],
            ["/remove_channel", "/set_payout"],
            ["/stats"]
        ]
        await update.message.reply_text(
            "✅ <b>Welcome to the Admin Panel!</b>\n"
            "Use the commands below to manage the bot:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("⛔️ <b>Incorrect password!</b>", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

@admin_required
async def add_channel(update: Update, context: CallbackContext):
    # Usage: /add_channel @channelusername
    args = context.args
    if not args or not args[0].startswith("@"):
        await update.message.reply_text("Usage: /add_channel @channelusername")
        return
    channel = args[0]
    if channel not in FORCE_JOIN_CHANNELS:
        FORCE_JOIN_CHANNELS.append(channel)
        config["FORCE_JOIN_CHANNELS"] = FORCE_JOIN_CHANNELS
        save_config(config)
        await update.message.reply_text(f"✅ Channel {channel} added to force-join list.")
    else:
        await update.message.reply_text(f"Channel {channel} is already in the force-join list.")

@admin_required
async def show_channels(update: Update, context: CallbackContext):
    txt = "Current force-join channels:\n" + "\n".join([f"• {ch}" for ch in FORCE_JOIN_CHANNELS])
    await update.message.reply_text(txt)

@admin_required
async def remove_channel(update: Update, context: CallbackContext):
    # Usage: /remove_channel @channelusername
    args = context.args
    if not args or not args[0].startswith("@"):
        await update.message.reply_text("Usage: /remove_channel @channelusername")
        return
    channel = args[0]
    if channel in FORCE_JOIN_CHANNELS:
        FORCE_JOIN_CHANNELS.remove(channel)
        config["FORCE_JOIN_CHANNELS"] = FORCE_JOIN_CHANNELS
        save_config(config)
        await update.message.reply_text(f"✅ Channel {channel} removed from force-join list.")
    else:
        await update.message.reply_text(f"Channel {channel} was not in the force-join list.")

@admin_required
async def gen_code(update: Update, context: CallbackContext):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /gen_code <points>")
        return
    amount = int(args[0])
    code = uuid4().hex[:8].upper()
    codes[code] = {"amount": amount, "used": False, "used_by": None}
    update_codes()
    await update.message.reply_text(
        f"🎟️ <b>Redeem Code Generated:</b>\n"
        f"<code>{code}</code>\n"
        f"Value: <b>{amount} points</b>",
        parse_mode=ParseMode.HTML
    )

@admin_required
async def broadcast(update: Update, context: CallbackContext):
    msg = update.message.text.split(None, 1)
    if len(msg) < 2:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    sent, fail = 0, 0
    for uid in users:
        try:
            await context.bot.send_message(uid, msg[1], parse_mode=ParseMode.HTML)
            sent += 1
        except:
            fail += 1
    await update.message.reply_text(f"📣 Sent to <b>{sent}</b> users. Failed: <b>{fail}</b>.", parse_mode=ParseMode.HTML)

@admin_required
async def ban(update: Update, context: CallbackContext):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    uid = args[0]
    banned.add(uid)
    update_banned()
    await update.message.reply_text(f"🚫 User {uid} has been banned.")

@admin_required
async def unban(update: Update, context: CallbackContext):
    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    uid = args[0]
    banned.discard(uid)
    update_banned()
    await update.message.reply_text(f"✅ User {uid} has been unbanned.")

@admin_required
async def set_payout(update: Update, context: CallbackContext):
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /set_payout @channel")
        return
    global PAYOUT_CHANNEL
    PAYOUT_CHANNEL = args[0]
    config["PAYOUT_CHANNEL"] = PAYOUT_CHANNEL
    save_config(config)
    await update.message.reply_text(f"✅ Payout channel set to {PAYOUT_CHANNEL}")

@admin_required
async def stats(update: Update, context: CallbackContext):
    total_users = len(users)
    total_banned = len(banned)
    total_balance = sum(u.get("balance", 0) for u in users.values())
    await update.message.reply_text(
        f"📊 <b>Bot Stats:</b>\n"
        f"• <b>Total Users:</b> {total_users}\n"
        f"• <b>Banned Users:</b> {total_banned}\n"
        f"• <b>Total Points in System:</b> {total_balance}",
        parse_mode=ParseMode.HTML
    )

async def help_cmd(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "🤖 <b>How to use this bot:</b>\n\n"
        "• <b>💸 Earn points</b> by inviting friends using /refer or the menu\n"
        "• <b>🎁 Withdraw</b> views by spending your points (1 point = 1 view)\n"
        "• <b>🔑 Redeem</b> codes for instant points\n"
        "• <b>📊 View your history</b> of withdrawals and codes\n"
        "• <b>💬 Need help?</b> Contact admin or use /help anytime!\n\n"
        "👑 <b>Pro Tip:</b> Stay active for exclusive codes & bonuses! 🚀",
        parse_mode=ParseMode.HTML
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(force_join_callback, pattern="check_join"))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance))
    app.add_handler(MessageHandler(filters.Regex("^🎁 Withdraw$"), withdraw))
    app.add_handler(MessageHandler(filters.Regex("^🔗 My Referral$"), refer))
    app.add_handler(MessageHandler(filters.Regex("^📊 History$"), history))
    app.add_handler(MessageHandler(filters.Regex("^🔑 Redeem$"), redeem))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Help$"), help_cmd))
    app.add_handler(CommandHandler("add_channel", add_channel))
    app.add_handler(CommandHandler("show_channels", show_channels))
    app.add_handler(CommandHandler("remove_channel", remove_channel))
    withdraw_conv = ConversationHandler(
        entry_points=[
            CommandHandler("withdraw", withdraw),
            MessageHandler(filters.Regex("^🎁 Withdraw$"), withdraw)
        ],
        states={
            WITHDRAW_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_link)],
            WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)]
        },
        fallbacks=[],
        allow_reentry=True
    )
    app.add_handler(withdraw_conv)
    redeem_conv = ConversationHandler(
        entry_points=[
            CommandHandler("redeem", redeem),
            MessageHandler(filters.Regex("^🔑 Redeem$"), redeem)
        ],
        states={
            REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_code)]
        },
        fallbacks=[],
        allow_reentry=True
    )
    app.add_handler(redeem_conv)
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin)],
        states={
            ADMIN_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_pass)]
        },
        fallbacks=[],
        allow_reentry=True
    )
    app.add_handler(admin_conv)
    app.add_handler(CommandHandler("gen_code", gen_code))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("set_payout", set_payout))
    app.add_handler(CommandHandler("stats", stats))
    print("🤖 Bot is running and ready to rock Telegram!")
    app.run_polling()

if __name__ == "__main__":
    main()