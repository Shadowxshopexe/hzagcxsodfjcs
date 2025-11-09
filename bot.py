import os, discord, json, requests, random, datetime, traceback
from discord.ext import commands, tasks
from discord.ui import View, Button

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= FILE HELPERS =================
def load(path):
    try: return json.load(open(path, "r", encoding="utf8"))
    except: return {}

def save(path, data):
    json.dump(data, open(path, "w", encoding="utf8"), indent=4)

# ================= LOAD CONFIG =================
config = load("config.json")
data = load("data.json")
logs = load("logs.json")

config["token"] = os.getenv("TOKEN", config.get("token"))
config["guild_id"] = os.getenv("GUILD_ID", config.get("guild_id"))
config["payment_channel"] = os.getenv("PAYMENT_CHANNEL", config.get("payment_channel"))
config["admin_channel"] = os.getenv("ADMIN_CHANNEL", config.get("admin_channel"))

# ================= PRICES =================
PRICES = {1:20, 3:40, 7:80, 15:150, 30:300}

def receipt():
    return "LS-" + "".join(random.choices("ABCDEFGHJKMNPQRSTUVWXYZ23456789", k=6))

async def pm(uid, msg):
    try:
        u = await bot.fetch_user(int(uid))
        await u.send(msg)
    except:
        pass

# ================= UI =================
class BuyMenu(View):
    def __init__(self):
        super().__init__(timeout=None)
        for d,p in PRICES.items():
            self.add_item(Button(label=f"{d} วัน | {p}฿", style=discord.ButtonStyle.green, custom_id=f"buy_{d}"))

class PayMethod(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.add_item(Button(label="ทรูมันนี่", style=discord.ButtonStyle.red, custom_id=f"tm_{uid}"))
        self.add_item(Button(label="ธนาคาร", style=discord.ButtonStyle.blurple, custom_id=f"bank_{uid}"))

class TM(View):
    def __init__(self, uid):
        super().__init__(timeout=None)
        self.add_item(Button(label="ซองทรู", style=discord.ButtonStyle.green, custom_id=f"gift_{uid}"))
        self.add_item(Button(label="สลิปทรู", style=discord.ButtonStyle.red, custom_id=f"slip_{uid}"))

# ================= READY =================
@bot.event
async def on_ready():
    print("✅ Bot Online (LuckyShop Full System)")
    check_expire.start()

# ================= BUY COMMAND =================
@bot.command()
async def buy(ctx):
    e = discord.Embed(
        title="💛 LuckyShop – ซื้อยศ",
        description="เลือกแพ็กเกจด้านล่าง",
        color=0xFFD700,
    )
    await ctx.send(embed=e, view=BuyMenu())

# ================= INTERACTION =================
@bot.event
async def on_interaction(i):
    try:
        cid = i.data.get("custom_id")
        uid = str(i.user.id)

        # -------- BUY PACKAGE --------
        if cid.startswith("buy_"):
            d = int(cid.split("_")[1])
            data[uid] = {"days": d, "status": "method"}
            save("data.json", data)
            return await i.response.send_message(embed=discord.Embed(title="💰 เลือกช่องทางชำระเงิน"), view=PayMethod(uid), ephemeral=True)

        # -------- BANK --------
        if cid.startswith("bank_"):
            uid = cid[5:]
            data[uid]["method"] = "bank"
            data[uid]["status"] = "slip"
            save("data.json", data)
            return await i.response.send_message("🏦 ส่งสลิปธนาคารที่นี่ได้เลย", ephemeral=True)

        # -------- TRUEMONEY MENU --------
        if cid.startswith("tm_"):
            uid = cid[3:]
            data[uid]["status"] = "tm_menu"
            save("data.json", data)
            return await i.response.send_message(embed=discord.Embed(title="📱 เลือกวิธีชำระ TrueMoney"), view=TM(uid), ephemeral=True)

        # -------- GIFT --------
        if cid.startswith("gift_"):
            uid = cid[5:]
            data[uid]["method"] = "gift"
            data[uid]["status"] = "gift"
            save("data.json", data)
            return await i.response.send_message("🎁 ส่งลิงก์ซองทรูมันนี่ที่นี่", ephemeral=True)

        # -------- SLIP --------
        if cid.startswith("slip_"):
            uid = cid[5:]
            data[uid]["method"] = "trueslip"
            data[uid]["status"] = "slip"
            save("data.json", data)
            return await i.response.send_message("📸 ส่งสลิปทรูมันนี่ที่นี่", ephemeral=True)

        # -------- APPROVE --------
        if cid.startswith("ok_"):
            t = cid[3:]

            await i.response.defer(ephemeral=True)

            if t not in data:
                return await i.followup.send("❌ ไม่พบข้อมูลคำสั่งซื้อ", ephemeral=True)

            info = data[t]
            d = info["days"]
            price = PRICES[d]

            guild = bot.get_guild(int(config["guild_id"]))
            member = guild.get_member(int(t))
            role = guild.get_role(int(config["roles"][str(d)]))

            now = datetime.datetime.now(datetime.timezone.utc).timestamp()
            old = info.get("expire", 0)

            expire = old + d*86400 if old > now else now + d*86400

            info["expire"] = expire
            info["status"] = "approved"
            save("data.json", data)

            # give role
            try: await member.add_roles(role)
            except:
                return await i.followup.send("❌ บอทไม่มีสิทธิ์เพิ่มยศ\nโปรดเลื่อน Role บอทขึ้นบนสุด", ephemeral=True)

            # log receipt
            rc = receipt()
            logs[rc] = {"uid":t,"days":d,"method":info["method"],"expire":expire}
            save("logs.json", logs)

            # send DM
            exp_text = datetime.datetime.utcfromtimestamp(expire).strftime("%d/%m/%Y %H:%M")
            await pm(t, f"✅ อนุมัติแล้ว!\nยศ: {d} วัน\nหมดอายุ: {exp_text}\nใบเสร็จ: {rc}")

            # send purchase log
            log_ch = bot.get_channel(1437099731921928296)
            embed = discord.Embed(title="✅ ซื้อยศสำเร็จ", color=0x00FF66)
            embed.add_field(name="👤 ผู้ซื้อ", value=f"<@{t}>", inline=False)
            embed.add_field(name="📦 แพ็กเกจ", value=f"{d} วัน", inline=False)
            embed.add_field(name="💰 ราคา", value=f"{price} บาท", inline=False)
            embed.add_field(name="💳 วิธีชำระเงิน", value=info["method"], inline=False)
            embed.add_field(name="📄 ใบเสร็จ", value=rc, inline=False)
            await log_ch.send(embed=embed)

            try: await i.message.delete()
            except: pass

            return await i.followup.send(f"✅ อนุมัติ <@{t}> เรียบร้อย!", ephemeral=True)

        # -------- DENY --------
        if cid.startswith("no_"):
            t = cid[3:]
            await i.response.defer(ephemeral=True)

            await pm(t, "❌ คำสั่งซื้อของคุณถูกปฏิเสธ")
            if t in data:
                del data[t]
                save("data.json", data)

            try: await i.message.delete()
            except: pass

            return await i.followup.send(f"❌ ปฏิเสธ <@{t}> แล้ว", ephemeral=True)

    except Exception as e:
        print("INTERACTION ERROR:", e)
        traceback.print_exc()

# ================= MESSAGE HANDLER =================
@bot.event
async def on_message(msg):
    if msg.author.bot: return

    uid = str(msg.author.id)
    channel = msg.channel.id

    if channel != int(config["payment_channel"]):
        return await bot.process_commands(msg)

    if uid not in data:
        return await bot.process_commands(msg)

    st = data[uid]["status"]

    try:
        # -------- GIFT --------
        if st == "gift" and "gift.truemoney.com" in msg.content:

            adm = bot.get_channel(int(config["admin_channel"]))
            days = data[uid]["days"]
            price = PRICES[days]

            v = View()
            v.add_item(Button(label="อนุมัติ", style=discord.ButtonStyle.green, custom_id=f"ok_{uid}"))
            v.add_item(Button(label="ไม่อนุมัติ", style=discord.ButtonStyle.red, custom_id=f"no_{uid}"))

            embed = discord.Embed(title="🎁 ซองทรูมันนี่", color=0xFFAA00)
            embed.add_field(name="ผู้ใช้", value=f"<@{uid}>")
            embed.add_field(name="แพ็กเกจ", value=f"{days} วัน — {price}฿")
            embed.add_field(name="ลิงก์ซอง", value=msg.content)

            await adm.send(embed=embed, view=v)
            await msg.delete()
            return

        # -------- SLIP --------
        if st == "slip" and msg.attachments:

            adm = bot.get_channel(int(config["admin_channel"]))
            files = [await a.to_file() for a in msg.attachments]

            days = data[uid]["days"]
            price = PRICES[days]
            method = data[uid]["method"]

            v = View()
            v.add_item(Button(label="อนุมัติ", style=discord.ButtonStyle.green, custom_id=f"ok_{uid}"))
            v.add_item(Button(label="ไม่อนุมัติ", style=discord.ButtonStyle.red, custom_id=f"no_{uid}"))

            embed = discord.Embed(title="💰 สลิปการชำระเงิน", color=0x00AAFF)
            embed.add_field(name="ผู้ใช้", value=f"<@{uid}>")
            embed.add_field(name="แพ็กเกจ", value=f"{days} วัน — {price}฿")
            embed.add_field(name="วิธีชำระเงิน", value=method)

            await adm.send(embed=embed, files=files, view=v)
            await msg.delete()
            return

    except Exception as e:
        print("MSG ERROR:", e)

    await bot.process_commands(msg)

# ================= AUTO REMOVE ROLE =================
@tasks.loop(seconds=30)
async def check_expire():
    guild = bot.get_guild(int(config["guild_id"]))
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()

    for uid, info in list(data.items()):
        if info.get("status") != "approved":
            continue

        exp = info.get("expire", 0)
        if now >= exp:
            role = guild.get_role(int(config["roles"][str(info["days"])]))
            member = guild.get_member(int(uid))

            try:
                await member.remove_roles(role)
            except:
                pass

            await pm(uid, "⏳ ยศของคุณหมดอายุแล้ว!")
            del data[uid]
            save("data.json", data)

# ================= RUN BOT =================
bot.run(config["token"])
