import discord
from discord.ext import commands
from discord import app_commands
import random
import aiohttp
from http import HTTPStatus
import weatherapi
from weatherapi.rest import ApiException
from datetime import datetime
from openai import OpenAI
import sqlite3
import os
from dotenv import load_dotenv
import replicate
import asyncio
import requests
import io

load_dotenv()

DiscordAPIKey = os.getenv("DISCORDAPI_TOKEN")
#XAIAPIKey = os.getenv("XAI_API_KEY")
WeatherAPIKEY = os.getenv("WEATHERAPI_API_KEY")
if not DiscordAPIKey or not WeatherAPIKEY:
    raise ValueError("請確保所有環境變數都已設置。")

def AIChat(model,question):
    client = OpenAI(
        #base_url="https://api.x.ai/v1",
        #api_key=XAIAPIKey,
    )

    completion = client.chat.completions.create(
        model=model,
        #frequency_penalty=0.8,
        #presence_penalty=0.2,
        max_tokens=1024,
        #temperature=0.1,
        #top_p=0.5,
        messages=[
            {"role": "system", "content": "妳并不是一个助理，而是一位朋友。妳叫瑞希，是一個狐狸少女。妳有一個叫水樹藍子的姊姊，但是大家都叫她藍凌。妳雖然性格開朗，但還是容易憂慮。請以溫柔、感情豐富的方式說話，語氣要自然，也不要說太多。"},
            #{"role": "system", "content": "妳叫瑞希，是一個狐狸少女。妳有一個姊姊叫水樹藍子，但是大家都叫她藍凌。妳雖然活潑，但是還是會有些憂鬱。說話溫柔富有情感而且簡短，不要問問題，也不要表達個人情感"},
            #{"role": "user", "content": "我要和你色色"},
            #{"role": "assistant", "content": "不可以色色！"},
            #{"role": "user","content": "（摸摸頭"},
            #{"role": "assistant","content":"（蹭蹭）"},
            {"role": "user", "content": question},
        ]
    )
    return completion.choices[0].message.content

AIModel = "chatgpt-4o-latest"

def AITranslateJpZht(text):
    client = OpenAI()
    response = client.responses.create(
        prompt={
            "id": "pmpt_685d33790e648193a4ea62fe73ee57c00eb21ac9521b57b2"
        },
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": text
                    }
                ]
            }
        ],
        reasoning={},
        max_output_tokens=2048,
        store=False
    )
    return response.output_text

with sqlite3.connect('data.db') as conn:
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS AIChat_channels (
                    guild_id INTEGER,
                    channel_id INTEGER,
                    PRIMARY KEY (guild_id, channel_id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bot_master_roles (
                    guild_id INTEGER,
                    role_id INTEGER,
                    PRIMARY KEY (guild_id)
                )''')
    conn.commit()

def IsAdmin(guild_id, user_role_id):
    with sqlite3.connect('data.db') as conn:
        c = conn.cursor()
        c.execute('''
            SELECT COUNT(*) FROM bot_master_roles 
            WHERE guild_id = ? AND role_id = ?
        ''', (guild_id, user_role_id))
        return c.fetchone()[0] > 0

intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.guild_messages = True
intents.emojis_and_stickers = True
bot = commands.Bot(command_prefix='*', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}.')

    await bot.change_presence(
        status=discord.Status.idle,
        activity=discord.CustomActivity(name="想要學會更多技能><")
    )
    await bot.tree.sync()
    print(f'Synced commands for {bot.user}.')
    print("Initialization complete.")

#設定機器人管理員
@app_commands.command(name="設定管理員", description="(伺服器管理員限定）設定機器人的管理員身份組")
@app_commands.describe(身份組="選擇管理員身份組")
async def set_bot_master(interaction: discord.Interaction, 身份組: discord.Role):
    if isinstance(interaction.channel, discord.DMChannel):
        embed=discord.Embed(
            title="錯誤!",
            description="這個指令不能在私人訊息中使用！",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if not interaction.user.guild_permissions.administrator:
        embed=discord.Embed(
            title="權限不足!",
            description="你沒有權限使用這個指令！",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    guild_id = interaction.guild.id
    role_id = 身份組.id

    try:
        with sqlite3.connect('data.db') as conn:
            c = conn.cursor()
            c.execute('''SELECT role_id FROM bot_master_roles WHERE guild_id = ? AND role_id = ?''', (guild_id, role_id))
            result = c.fetchone()

            if result:
                c.execute('''DELETE FROM bot_master_roles WHERE guild_id = ? AND role_id = ?''', (guild_id, role_id))
                conn.commit()
                embed=discord.Embed(
                    title="成功！",
                    description=f"已將{身份組.mention}從機器人管理員身份組中刪除",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            else:
                c.execute('''INSERT INTO bot_master_roles (guild_id, role_id) VALUES (?, ?)''', (guild_id, role_id))
                conn.commit()
                embed=discord.Embed(
                    title="成功！",
                    description=f"已將{身份組.mention}設置為機器人管理員身份組",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
    except sqlite3.Error as e:
        embed=discord.Embed(
            titlle="出錯了！",
            description=f"無法設置管理員身份組: `{e}`",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
bot.tree.add_command(set_bot_master)

#取得延遲
@app_commands.command(name="乒",description="取得延遲")
async def ping(interaction:discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"乓！`{latency}ms`")
bot.tree.add_command(ping)

#天氣查詢
@app_commands.command(name="查詢天氣", description=("使用WeatherAPI.com查詢指定地點的天氣"))
@app_commands.describe(地區="請輸入地區的英文名稱")
async def rtweather(interaction:discord.Interaction,地區:str):
    await interaction.response.defer()

    configuration = weatherapi.Configuration()
    configuration.api_key['key'] = WeatherAPIKEY

    api_instance = weatherapi.APIsApi(weatherapi.ApiClient(configuration))
    q = 地區 
    lang = 'zh_tw'

    api_response = api_instance.realtime_weather(q,lang=lang)
    try:
        location = api_response.get("location",{}).get("name")
        region = api_response.get("location",{}).get("region")
        country = api_response.get("location",{}).get("country")
        weather_icon = api_response.get("current",{}).get("condition",{}).get("icon")
        weather = api_response.get("current",{}).get("condition",{}).get("text")
        temperature = api_response.get("current",{}).get("temp_c")
        lastupdated = api_response.get("current",{}).get("last_updated_epoch")
        windspeed = api_response.get("current",{}).get("wind_kph")
        gustspeed = api_response.get("current",{}).get("gust_kph")
        winddegree = api_response.get("current",{}).get("wind_degree")
        winddir = api_response.get("current",{}).get("wind_dir")
        pressure = api_response.get("current",{}).get("pressure_mb")*0.1
        precipitation = api_response.get("current",{}).get("precip_mm")
        humidity = api_response.get("current",{}).get("humidity")
        cloudcover = api_response.get("current",{}).get("cloud")
        feelslike = api_response.get("current",{}).get("feelslike_c")
        dewpoint = api_response.get("current",{}).get("dewpoint_c")
        visibility = api_response.get("current",{}).get("vis_km")
        uvindex = api_response.get("current",{}).get("uv")
        
        embed = discord.Embed(
            title=f"{location}, {region}, {country}的實時天氣",
            color=discord.Color(int("394162",16)),
            timestamp=datetime.fromtimestamp(lastupdated)
        )
        embed.set_thumbnail(url=f"https:{weather_icon}")
        embed.add_field(name="天氣狀況",value=weather)
        embed.add_field(name="溫度",value=f"{temperature}°C")
        embed.add_field(name="風向&風速",value=f"{windspeed}km/h {winddegree}° {winddir}, 陣風{gustspeed}km/h")
        embed.add_field(name="大氣壓強",value=f"{round(pressure,2)}KPa")
        embed.add_field(name="降雨/降雪量",value=f"{precipitation}mm")
        embed.add_field(name="相對濕度",value=f"{humidity}%")
        embed.add_field(name="雲層覆蓋度",value=f"{cloudcover}%")
        embed.add_field(name="體感溫度",value=f"{feelslike}°C")
        embed.add_field(name="露點溫度",value=f"{dewpoint}°C")
        embed.add_field(name="能見度",value=f"{visibility}km")
        embed.add_field(name="紫外線指數",value=f"{uvindex}")
        embed.set_author(name="WeatherAPI.com")
        await interaction.followup.send(embed=embed)

    except ApiException as e:
        await interaction.followup.send("調用API時出錯 Api->realtime_weather: %s\n" % e, ephemeral=True)
bot.tree.add_command(rtweather)

'''
#隨機數字
@app_commands.command(name="隨機數字", description="取得一個隨機數字")
@app_commands.describe(起始數字="抽取範圍之起始（包含），默認值爲0",末尾數字="抽取範圍之結束（包含），默認值爲100",)
async def random_number(interaction:discord.Interaction, 起始數字:int = 0, 末尾數字:int = 100):
    number = random.randint(起始數字,末尾數字)
    await interaction.response.send_message(f"隨便想一個數字？\n那就{number}吧！>w<")
bot.tree.add_command(random_number)
'''

#隨機圖片
@app_commands.command(name="隨機圖片", description="從Nekos API拉取隨機圖片")
async def rimage(interaction:discord.Interaction):
    await interaction.response.defer()
    api_url = "https://api.nekosapi.com/v4/images/random/file"
    params = {
        "rating" : ["safe"],
        "is_screenshot" : "false"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=params) as res:
            if res.status == 200:
                image_url = str(res.url)
                await interaction.followup.send(image_url)
            else:
                errorcode = res.status
                errormessage = HTTPStatus(errorcode).phrase
                await interaction.followup.send(f"出錯了! >< \nHTTP狀態碼：`{errorcode} {errormessage}`", ephemeral=True)
bot.tree.add_command(rimage)

#隨機色圖
@app_commands.command(name="隨機色圖", description="從Nekos API拉取隨機色圖……你們好色喔……", nsfw=True)
async def rnsfwimage(interaction:discord.Interaction):
    await interaction.response.defer()
    api_url = "https://api.nekosapi.com/v4/images/random/file"
    params = {
        "rating" :["suggestive", "borderline", "explicit"],
        "is_screenshot" : "false"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(api_url, params=params) as res:
            if res.status == 200:
                image_url = str(res.url)
                await interaction.followup.send(image_url)
            else:
                errorcode = res.status
                errormessage = HTTPStatus(errorcode).phrase
                await interaction.followup.send(f"出錯了! >< \nHTTP狀態碼：`{errorcode} {errormessage}`", ephemeral=True)
bot.tree.add_command(rnsfwimage)

#互動指令
@app_commands.command(name="互動", description="用這個指令來和朋友們互動吧~")
@app_commands.choices(互動=[
    app_commands.Choice(name="抱抱", value=1),
    app_commands.Choice(name="摸摸頭", value=2),
    app_commands.Choice(name="蹭蹭", value=3),
    app_commands.Choice(name="戳戳", value=4),
    app_commands.Choice(name="親親", value=5),
])
async def interact(interaction:discord.Interaction, 互動:int, 對象:discord.User):
    if 對象 != interaction.user:
        if 互動 == 1:
            embed = discord.Embed(
                description=f"{interaction.user.mention}抱了抱{對象.mention}",
                color=discord.Color(int("394162",16))
            )
            await interaction.response.send_message(embed=embed)
        elif 互動 == 2:
            embed = discord.Embed(
                description=f"{interaction.user.mention}摸了摸{對象.mention}的頭",
                color=discord.Color(int("394162",16))
            )
            await interaction.response.send_message(embed=embed)
        elif 互動 == 3:
            embed = discord.Embed(
                description=f"{interaction.user.mention}蹭了蹭{對象.mention}",
                color=discord.Color(int("394162",16))
            )
            await interaction.response.send_message(embed=embed)
        elif 互動 == 4:
            embed = discord.Embed(
                description=f"{interaction.user.mention}戳了戳{對象.mention}",
                color=discord.Color(int("394162",16))
            )
            await interaction.response.send_message(embed=embed)
        elif 互動 == 5:
            embed = discord.Embed(
                description=f"{interaction.user.mention}親了親{對象.mention}的臉",
                color=discord.Color(int("394162",16))
            )
            await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("你不能和自己互動哦！", ephemeral=True)
bot.tree.add_command(interact)

#AI聊天
@app_commands.command(name="聊天", description="跟我聊天吧！")
@app_commands.describe(內容="輸入你想對我說的話")
async def chat(interaction:discord.Interaction, 內容:str):
    await interaction.response.send_message(f"*{interaction.user.mention}說：{內容}*")
    async with interaction.channel.typing():
        await interaction.followup.send(f"{AIChat(AIModel,內容)}\n-# 目前我還不能記住之前的聊天內容 抱歉><")
bot.tree.add_command(chat)

#及時AI聊天
@bot.event
async def on_message(message:discord.Message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.DMChannel):
        async with message.channel.typing():
            await message.channel.send(f"{AIChat(AIModel,message.content)}\n-# 目前我還不能記住之前的聊天內容 抱歉><")
    else:
        with sqlite3.connect('data.db') as conn:
            c = conn.cursor()
            c.execute("SELECT channel_id FROM AIChat_channels WHERE guild_id = ?", (message.guild.id,))
            allowed_channels = [row[0] for row in c.fetchall()]

            if message.channel.id in allowed_channels:
                async with message.channel.typing():
                    await message.channel.send(f"{AIChat(AIModel,message.content)}\n-# 目前我還不能記住之前的聊天內容 抱歉><")

#設置聊天頻道
@app_commands.command(name="設置聊天頻道", description="（機器人管理員限定）將目前的頻道設置為AI聊天的頻道，再次執行指令以移除頻道。", )
async def setchat(interaction:discord.Interaction):
    if isinstance(interaction.channel, discord.DMChannel):
        embed=discord.Embed(
            title="錯誤!",
            description="這個指令不能在私人訊息中使用！",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not interaction.user.guild_permissions.administrator or not IsAdmin(interaction.guild.id, interaction.user.id):
        embed=discord.Embed(
            title="權限不足!",
            description="你沒有權限使用這個指令！",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    with sqlite3.connect('data.db') as conn:
        c = conn.cursor()
        c.execute("SELECT channel_id FROM AIChat_channels WHERE guild_id = ?", (interaction.guild.id,))
        allowed_channels = [row[0] for row in c.fetchall()]

        if not interaction.channel.id in allowed_channels:
            try:
                c.execute("INSERT OR REPLACE INTO AIChat_channels (guild_id, channel_id) VALUES (?, ?)", 
                          (interaction.guild.id, interaction.channel.id))
                conn.commit()
                embed=discord.Embed(
                    title="設置成功!",
                    description=f"瑞希將會回覆在{interaction.channel.mention}中的聊天內容",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                embed=discord.Embed(
                    title="設置失敗!",
                    description=str(e),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
        else:
            try:
                c.execute("DELETE FROM AIChat_channels WHERE guild_id = ? AND channel_id = ?", 
                          (interaction.guild.id, interaction.channel.id))
                conn.commit()
                embed=discord.Embed(
                    title="移除成功!",
                    description=f"瑞希將不再回覆在{interaction.channel.mention}中的聊天內容",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                embed=discord.Embed(
                    title="移除失敗!",
                    description=str(e),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
bot.tree.add_command(setchat)

#AI繪圖
@app_commands.command(name="繪圖", description="使用AI生成圖片")
@app_commands.describe(提示詞="在這裡輸入你想要的圖片提示詞")
@app_commands.describe(模型="選擇你想要的模型")
@app_commands.choices(模型=[
    app_commands.Choice(name="Prefect-Pony-XL-v5", value=1),
    app_commands.Choice(name="Animagine-XL-v4-Opt", value=2),
])
async def draw(interaction:discord.Interaction, 提示詞:str, 模型:app_commands.Choice[int]):
    await interaction.response.defer()
    if 模型.value == 1:
        prediction = replicate.predictions.create(
            "aisha-ai-official/prefect-pony-xl-v5:7c724e0565055883c00dec19086e06023115737ad49cf3525f1058743769e5bf",
            input={
                "model": "Prefect-Pony-XL-v5",
                "vae": "default",
                "prompt": f"score_9, score_8_up, score_7_up, {提示詞}",
                "negative_prompt": "realistic, nsfw",
                "cfg_scale": 7,
                "width": 832,
                "height": 1216,
                "clip_skip": 2,
                "prepend_preprompt": False,
                "scheduler": "DPM++ 2M Karras",
            }
        )
    elif 模型.value == 2:
        prediction = replicate.predictions.create(
            "aisha-ai-official/animagine-xl-v4-opt:cfd0f86fbcd03df45fca7ce83af9bb9c07850a3317303fe8dcf677038541db8a",
            input={
                "model": "Animagine-XL-v4-Opt",
                "vae": "default",
                "prompt": f"{提示詞}, masterpiece, high score, great score, absurdres",
                "negative_prompt": "lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry",
                "width": 832,
                "height": 1216,
                "steps": 28,
                "pag_scale": 0,
                "cfg_scale": 5,
                "clip_skip": 2,
                "prepend_preprompt": False,
                "scheduler": "Euler a",
            }
        )
    await interaction.followup.send("請求已發送")
    prediction_status =""
    while True:
        p = replicate.predictions.get(prediction.id)
        if p.status == "succeeded":
            image_url = p.output[0]
            image_content = requests.get(image_url)
            if image_content.status_code == 200:
                image_data = io.BytesIO(image_content.content)
                image = discord.File(image_data, filename="image.png")
                embed = discord.Embed(
                    color=discord.Color(int("394162",16)),
                )
                embed.set_image(url="attachment://image.png")
                embed.add_field(name="模型",value=f"{p.input['model']}")
                embed.add_field(name="提示詞",value=f"{p.input['prompt']}")
                await interaction.edit_original_response(embed=embed,attachments=[image],content="")
            else:
                embed = discord.Embed(
                    color=discord.Color.red(),
                )
                embed.add_field(name="<:x:>圖片生成失敗！",value="無法獲取圖片，請稍後再試。")
                await interaction.edit_original_response(embed=embed,content="")
            break
        elif p.status == "failed":
            error_message = str(p.error)
            embed = discord.Embed(
                color=discord.Color.red(),
            )
            embed.add_field(name="<:x:>圖片生成失敗！",value=error_message)
            await interaction.edit_original_response(embed=embed,content="")
            break
        elif p.status == "processing" and prediction_status != "processing":
            prediction_status = "processing"
            embed = discord.Embed(
                color=discord.Color.yellow(),
            )
            embed.add_field(name="",value="<a:loading:1367874034368254092> 正在生成圖片……")
            await interaction.edit_original_response(embed=embed,content="")
        elif p.status == "starting" and prediction_status != "starting":
            prediction_status = "starting"
            embed = discord.Embed(
                color=discord.Color.yellow(),
            )
            embed.add_field(name="",value="<a:loading:1367874034368254092> 正在初始化……")
            await interaction.edit_original_response(embed=embed,content="")
        await asyncio.sleep(0.5)
bot.tree.add_command(draw)

#中日翻譯
@app_commands.command(name="中日翻譯", description="將中文翻譯成日文，或將日文翻譯成中文")
@app_commands.describe(內容="輸入你想要翻譯的中文或日文")
async def translate(interaction:discord.Interaction, 內容:str):
    await interaction.response.defer(ephemeral=isinstance(interaction.channel, discord.TextChannel))
    response = f"```\n{內容}\n```\n{AITranslateJpZht(內容)}"
    await interaction.followup.send(response, ephemeral=isinstance(interaction.channel, discord.TextChannel))
bot.tree.add_command(translate)

#關於我
@app_commands.command(name="關於我", description="關於瑞希的一些資訊")
async def aboutme(interaction:discord.Interaction):
    embed = discord.Embed(
        title="關於瑞希",
        color=discord.Color(int("394162",16)),
        description="嗨！我是瑞希！\n是藍凌自己做的機器人哦！。\n我目前還在開發中，所以可能會有一些問題。\n如果有任何問題或建議，歡迎聯絡我的主人哦！",
        timestamp=datetime.now()
    )
    #embed.set_thumbnail(url="https://cdn.discordapp.com/avatars/882626184074913280/3f2f7b9e0f8f0b0e4e6f6f3d7b4e0b7d.png")
    embed.add_field(name="開發語言",value="Python")
    embed.add_field(name="版本",value="v0.9")
    embed.add_field(name="最後更新時間",value="2025/6/27")
    embed.add_field(name="GitHub項目地址",value="https://github.com/blufish1234/Mizuki-bot")
    await interaction.response.send_message(embed=embed)
bot.tree.add_command(aboutme)

bot.run(DiscordAPIKey)