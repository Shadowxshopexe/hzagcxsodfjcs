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
        u = await bot.fetch_user(int(uid))
        await u.send(msg)
    except:
        pass

# ---------------- READY ----------------
@bot.event
async def on_ready():
    print("✅ LuckyShop Bot Ready (Fixed Interaction)")
    check_expire.start()

# ---------------- BUY COMMAND ----------------
@bot.command()
async def buy(ctx):
    e = discord.Embed(
        title="💛 Lucky Shop – ซื้อยศ",
        description="เลือกแพ็กเกจที่ต้องการด้านล่าง",
        color=0xFFD700
    )
    e.set_thumbnail(url="attachment://logo.png")
    await ctx.send(embed=e,
                   file=discord.File("logo.png"),
                   view=BuyMenu())

# ---------------- INTERACTION ----------------
@bot.event
async def on_interaction(i):
    try:
        cid = i.data.get("custom_id", "")
        uid = str(i.user.id)

        # -------- BUY ----------
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

            return await i.response.send_message("🏦 ส่งสลิปธนาคารได้เลย", ephemeral=True)

        # -------- TM MENU ----------
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

            return await i.response.send_message("🎁 ส่งลิงก์ซองทรูในห้องนี้", ephemeral=True)

        # -------- SLIP ----------
        if cid.startswith("slip_"):
            uid = cid[5:]
            data[uid]["method"] = "trueslip"
            data[uid]["status"] = "slip"
            save("data.json", data)

            return await i.response.send_message("📸 ส่งสลิปทรูในห้องนี้", ephemeral=True)

        # -------- ✅ APPROVE ----------
        if cid.startswith("ok_"):
            t = cid[3:]                 # user ID
            info = data[t]
            d = info["days"]

            g = bot.get_guild(int(config["guild_id"]))
            m = g.get_member(int(t))
            r = g.get_role(int(config["roles"][str(d)]))

            now = datetime.datetime.utcnow().timestamp()

            # ✅ ทบวันถ้ายังไม่หมดอายุ
            if info.get("expire", 0) > now:
                exp = info["expire"] + d * 86400
            else:
                exp = now + d * 86400

            info["expire"] = exp
            info["status"] = "approved"
            save("data.json", data)

            # ✅ Add role
            if m and r:
                await m.add_roles(r)

            # ✅ บันทึกใบเสร็จ
            rc = receipt()
            logs[rc] = {
                "uid": t,
                "days": d,
                "method": info["method"],
                "expire": exp
            }
            save("logs.json", logs)

            # ✅ DM ลูกค้า
            exp_dt = datetime.datetime.utcfromtimestamp(exp).strftime("%d/%m/%Y %H:%M")
            await pm(t, f"✅ อนุมัติแล้ว!\nยศ {d} วัน\nหมดอายุ: {exp_dt}\nใบเสร็จ: {rc}")

            # ✅ ต้องตอบ interaction ก่อนลบข้อความ
            await i.response.send_message(f"✅ อนุมัติ <@{t}> แล้ว", ephemeral=True)

            # ✅ ค่อยลบข้อความแอดมิน
            try:
                await i.message.delete()
            except:
                pass

            return

        # -------- ❌ DENY ----------
        if cid.startswith("no_"):
            t = cid[3:]

            await pm(t, "❌ การชำระเงินของคุณไม่ผ่านตรวจสอบ")

            if t in data:
                del data[t]
                save("data.json", data)

            # ✅ ตอบ interaction ก่อน
            await i.response.send_message(f"❌ ปฏิเสธ <@{t}> แล้ว", ephemeral=True)

            # ✅ ลบข้อความแอดมิน
            try:
                await i.message.delete()
            except:
                pass

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
    now = datetime.datetime.utcnow().timestamp()
    g = bot.get_guild(int(config["guild_id"]))
    rem = []

    for uid, info in list(data.items()):
        if info.get("status") != "approved":
            continue

        if now >= info.get("expire", 0):
            m = g.get_member(int(uid))
            r = g.get_role(int(config["roles"][str(info["days"])]))

            if m and r:
                await m.remove_roles(r)

            await pm(uid, "⏳ ยศของคุณหมดอายุแล้ว")
            rem.append(uid)

    for u in rem:
        del data[u]

    if rem:
        save("data.json", data)

# ---------------- RUN ----------------
bot.run(config["token"])
