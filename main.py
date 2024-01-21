import discord
import os
from discord.ext import commands
from discord import app_commands
from bot import Kirito
from command_list import command_list
from datetime import datetime
from multiprocessing import Pool
from settings import *

bot = Kirito()

def make_command(command):
    name = command['name']
    @bot.hybrid_command(name=name, description=command['description'])
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def name(ctx: commands.Context):
        await ctx.send(command['response'])

for command in command_list:
    make_command(command)

def parse_image(filename):
    return bot.parse_image(filename)

@bot.event
async def on_ready():
    print("online")
    bot.get_fashion_automatically.start()
    bot.show_treasure_statistics.start()

@bot.event
async def on_message(message):
    try:
        if message.author.bot:
            return
        if message.channel.id == TREASURE_CHANNEL:
            filenames = await bot.parse_attachments(message.attachments)
            if len(filenames) == 0:
                return
            if __name__ == '__main__':
                with Pool(os.cpu_count()) as pool:
                    texts = pool.map(parse_image, filenames)
                await bot.parse_texts(texts, message)

        await bot.process_commands(message)
    except Exception as e:
        bot.write_log(e)

@bot.hybrid_command(name='時裝', description='隨機PO出時裝')
@app_commands.guilds(discord.Object(id=SERVER_ID))
async def fashion(ctx: commands.Context):
    try:
        channel = bot.get_channel(ctx.channel.id)
        message = await ctx.send('尋找圖片中...')
        url = 'not get fashion yet'
        name, file_path, url = await bot.get_fashion()
        await message.delete()
        await channel.send(f"【{name}】", file=discord.File(file_path))
        os.remove(file_path)
    except Exception as e:
        bot.write_log(f"url: {url}\n{e}")
        await channel.send('發生錯誤，再試一次', file=discord.File(f"{IMAGE_DIR}/broken_face.png"))

@bot.hybrid_command(name='kirito', description='與桐人對話')
@app_commands.guilds(discord.Object(id=SERVER_ID))
async def kirito(ctx: commands.Context, say: str):
    try:
        if len(say) == 0:
            return
        await ctx.send(f"{ctx.author.name}: {say}")
        thinking = await ctx.send('大腦在星爆', file=discord.File(f"{IMAGE_DIR}/starburst.gif"))
        response = await bot.generate_response(say, 1)
        await thinking.delete()
        await ctx.send(response)
    except Exception as e:
        bot.write_log(e)
        await thinking.delete()
        await ctx.send('桐人停止了思考，再試一次', file=discord.File(f"{IMAGE_DIR}/broken_face.png"))

@bot.hybrid_command(name='查詢戰利品紀錄', description='日期格式: yyyyMMdd')
@app_commands.guilds(discord.Object(id=SERVER_ID))
@app_commands.describe(開始日期="開始日期", 結束日期="結束日期")
async def check_treasure_records(ctx: commands.Context, 開始日期: str, 結束日期: str):
    start_date = 開始日期
    end_date = 結束日期
    if start_date.isnumeric() == False or len(start_date) != 8:
        await ctx.send("開始日期格式錯誤")
        return
    if end_date.isnumeric() == False or len(end_date) != 8:
        await ctx.send("結束日期格式錯誤")
        return
    start_date = datetime.strptime(start_date, '%Y%m%d')
    end_date = datetime.strptime(end_date, '%Y%m%d')
    if start_date >= end_date:
        await ctx.send("開始時間必須小於結束時間")
        return
    start_date = start_date.strftime('%Y-%m-%d')
    end_date = end_date.strftime('%Y-%m-%d')
    try:
        embed = await bot.show_treasure_statistics(start_date, end_date)
        if embed == None:
            await ctx.send(f"{start_date} ~ {end_date} 該區間查無紀錄")
            return
        await ctx.send(embed=embed)
    except Exception as e:
        bot.write_log(e)
        await ctx.send('查詢失敗', file=discord.File(f"{IMAGE_DIR}/broken_face.png"))

if __name__ == '__main__':
    bot.run(TOKEN)