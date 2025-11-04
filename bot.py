import os, discord, json, requests, random, datetime, traceback
from discord.ext import commands, tasks
from discord.ui import View, Button

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- LOAD & SAVE ----------------
def load(path):
    try:
        return json.load(open(path, "r", encoding="utf8"))
    except:
        return {}

def save(path, data):
    json.dump(data, open(path, "w", encoding="utf8"), indent=4)

# ---------------- CONFIG ----------------
config = load("config.json")

# Railway ENV override
config["token"] = os.getenv("TOKEN", config.get("token"))
config["guild_id"] = os.getenv("GUILD_ID", config.get("guild_id"))
config["payment_channel"] = os.getenv("PAYMENT_CHANNEL", config.get("payment_channel"))
config["admin_channel"] = os.getenv("ADMIN_CHANNEL", config.get("admin_channel"))

data = load("data.json")
logs = load("logs.json")

# ---------------- DOWNLOAD LOGO ----------------
if not os.path.exists("logo.png"):
    try:
        r = requests.get(config.get("bank_image", ""), timeout=5)
        open("logo.png", "wb").write(r.content)
    except:
        pass

def receipt():
    return "LS-" + "".join(random.choices("ABCDEFGHJKMNPQRSTUVWXYZ23456789", k=6))

# ---------------- UI BUTTONS ----------------
class BuyMenu(View):
    def __init__(self):
        super().__init__(timeout=None)
        packs = [(1,20),(3,40),(7,80),(15,150),(30,300)]
        for d,p in packs:
            self.add_item(Button(label=f"{d} วัน | {p}฿",
                                 style=discord.ButtonStyle.green,
                                 custom_id=f"buy_{d}"))

class PayMethod(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.add_item(Button(label="ทรูมันนี่", emoji="📱", style=discord.ButtonStyle.red, custom_id=f"tm_{uid}"))
        self.add_item(Button(label="ธนาคาร", emoji="🏦", style=discord.ButtonStyle.blurple, custom_id=f"bank_{uid}"))

class TM(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.add_item(Button(label="ซองทรู", style=discord.ButtonStyle.green, custom_id=f"gift_{uid}"))
        self.add_item(Button(label="สลิปทรู", style=discord.ButtonStyle.red, custom_id=f"slip_{uid}"))

async def pm(uid, msg):
    try:
        user = await bot.fetch_user(int(uid))
        await user.send(msg)
    except:
        pass

# ---------------- READY ----------------
@bot.event
async def on_ready():
    print("✅ LuckyShop Bot Ready (DEFER FIX VERSION)")
    check_expire.start()

# ---------------- BUY COMMAND ----------------
@bot.command()
async def buy(ctx):
    e = discord.Embed(
        title="💛 Lucky Shop – ซื้อยศ",
        description="เลือกแพ็กเกจด้านล่าง",
        color=0xFFD700
    )
    e.set_thumbnail(url="attachment://logo.png")
    await ctx.send(embed=e,
                   file=discord.File("logo.png"),
                   view=BuyMenu())

# ---------------- INTERACTION HANDLER ----------------
@bot.event
async def on_interaction(i):
    try:
        cid = i.data.get("custom_id", "")
        uid = str(i.user.id)

        # -------- BUY PACKAGE ----------
        if cid.startswith("buy_"):
            d = int(cid.split("_")[1])
            data[uid] = {"days": d, "status": "method"}
            save("data.json", data)

            e = discord.Embed(title="💰 เลือกช่องทางชำระเงิน", color=0xFFD700)
            return await i.response.send_message(embed=e, view=PayMethod(uid), ephemeral=True)

        # -------- BANK ----------
        if cid.startswith("bank_"):
            uid = cid[5:]
            data[uid]["method"] = "bank"
            data[uid]["status"] = "slip"
            save("data.json", data)

            return await i.response.send_message("🏦 ส่งสลิปธนาคารในห้องนี้ได้เลย", ephemeral=True)

        # -------- TRUE MONEY MENU ----------
        if cid.startswith("tm_"):
            uid = cid[3:]
            data[uid]["status"] = "choose_tm"
            save("data.json", data)

            e = discord.Embed(title="📱 TrueMoney",
                              description="เลือกวิธีชำระเงิน",
                              color=0xFF8800)
            return await i.response.send_message(embed=e, view=TM(uid), ephemeral=True)

        # -------- GIFT ----------
        if cid.startswith("gift_"):
            uid = cid[5:]
            data[uid]["method"] = "gift"
            data[uid]["status"] = "gift"
            save("data.json", data)

            return await i.response.send_message("🎁 ส่งลิงก์ซองทรูมันนี่ได้เลย", ephemeral=True)

        # -------- SLIP ----------
        if cid.startswith("slip_"):
            uid = cid[5:]
            data[uid]["method"] = "trueslip"
            data[uid]["status"] = "slip"
            save("data.json", data)

            return await i.response.send_message("📸 ส่งสลิปทรูมันนี่ในห้องนี้", ephemeral=True)

        # ✅✅✅ -------- APPROVE (แก้ interaction failed แล้ว) ----------
        if cid.startswith("ok_"):
            t = cid[3:]
            info = data[t]
            d = info["days"]

            g = bot.get_guild(int(config["guild_id"]))
            member = g.get_member(int(t))
            role = g.get_role(int(config["roles"][str(d)]))

            # ✅ 1) DEFER interaction (กัน interaction failed)
            await i.response.defer(ephemeral=True)

            now = datetime.datetime.now(datetime.timezone.utc).timestamp()

            # ✅ ถ้ายังมีเวลาเหลือ → ต่ออายุ
            if info.get("expire", 0) > now:
                expire_time = info["expire"] + d * 86400
            else:
                expire_time = now + d * 86400

            info["expire"] = expire_time
            info["status"] = "approved"
            save("data.json", data)

            # ✅ ให้ ROLE
            if member and role:
                await member.add_roles(role)

            # ✅ ใบเสร็จ
            rc = receipt()
            logs[rc] = {
                "uid": t,
                "days": d,
                "method": info["method"],
                "expire": expire_time
            }
            save("logs.json", logs)

            # ✅ DM ลูกค้า
            expires = datetime.datetime.utcfromtimestamp(expire_time).strftime("%d/%m/%Y %H:%M")
            await pm(t, f"✅ อนุมัติแล้ว!\nยศ {d} วัน\nหมดอายุ: {expires}\nใบเสร็จ: {rc}")

            # ✅ 2) ลบข้อความแอดมิน
            try:
                await i.message.delete()
            except:
                pass

            # ✅ 3) ตอบกลับ followup (ปลอดภัยที่สุด)
            await i.followup.send(f"✅ อนุมัติ <@{t}> แล้ว!", ephemeral=True)
            return

        # ✅✅✅ -------- DENY ----------
        if cid.startswith("no_"):
            t = cid[3:]

            # DEFER ก่อน
            await i.response.defer(ephemeral=True)

            await pm(t, "❌ การชำระของคุณไม่ผ่านตรวจสอบ")

            if t in data:
                del data[t]
                save("data.json", data)

            try:
                await i.message.delete()
            except:
                pass

            await i.followup.send(f"❌ ปฏิเสธ <@{t}> แล้ว", ephemeral=True)
            return

    except Exception as e:
        print("INTERACTION ERR:", e)
        traceback.print_exc()

# ---------------- MESSAGE HANDLER ----------------
@bot.event
async def on_message(msg):
    if msg.author.bot:
        return

    uid = str(msg.author.id)

    if msg.channel.id != int(config["payment_channel"]):
        return await bot.process_commands(msg)

    if uid not in data:
        return await bot.process_commands(msg)

    st = data[uid]["status"]

    try:
        # -------- GIFT --------
        if st == "gift" and "gift.truemoney.com" in msg.content:
            adm = bot.get_channel(int(config["admin_channel"]))

            v = View()
            v.add_item(Button(label="อนุมัติ", style=discord.ButtonStyle.green, custom_id=f"ok_{uid}"))
            v.add_item(Button(label="ไม่อนุมัติ", style=discord.ButtonStyle.red, custom_id=f"no_{uid}"))

            await adm.send(f"🎁 ซองทรูจาก <@{uid}>:\n{msg.content}", view=v)
            return await msg.delete()

        # -------- SLIP --------
        if st == "slip" and msg.attachments:
            adm = bot.get_channel(int(config["admin_channel"]))
            files = [await a.to_file() for a in msg.attachments]

            v = View()
            v.add_item(Button(label="อนุมัติ", style=discord.ButtonStyle.green, custom_id=f"ok_{uid}"))
            v.add_item(Button(label="ไม่อนุมัติ", style=discord.ButtonStyle.red, custom_id=f"no_{uid}"))

            await adm.send(f"💰 สลิปจาก <@{uid}>", files=files, view=v)
            return await msg.delete()

    except Exception as e:
        print("MSG ERR:", e)

    await bot.process_commands(msg)

# ---------------- AUTO REMOVE ROLE ----------------
@tasks.loop(minutes=1)
async def check_expire():
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    guild = bot.get_guild(int(config["guild_id"]))
    remove_list = []

    for uid, info in list(data.items()):
        if info.get("status") != "approved":
            continue

        if now >= info.get("expire", 0):
            member = guild.get_member(int(uid))
            role = guild.get_role(int(config["roles"][str(info["days"])]))

            if member and role:
                await member.remove_roles(role)

            await pm(uid, "⏳ ยศของคุณหมดอายุแล้ว")
            remove_list.append(uid)

    for u in remove_list:
        del data[u]

    if remove_list:
        save("data.json", data)

# ---------------- RUN ----------------
bot.run(config["token"])
