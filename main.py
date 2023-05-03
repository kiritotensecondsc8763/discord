import discord
import os
from discord.ext import commands
from discord import app_commands
from bot import Kirito
from keep_alive import keep_alive
from command_list import command_list
from settings import *

bot = Kirito()

@bot.event
async def on_ready():
    print("online")
    bot.get_fashion_automatically.start()
    bot.show_treasure_statistics.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id == TREASURE_CHANNEL:
        if len(message.attachments) == 0:
            return
        await bot.parse_attachments(message)

    await bot.process_commands(message)

def make_command(command):
    name = command['name']
    @bot.hybrid_command(name=name, description=command['description'])
    @app_commands.guilds(discord.Object(id=SERVER_ID))
    async def name(ctx: commands.Context):
        await ctx.send(command['response'])

for command in command_list:
    make_command(command)

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
    except Exception as e:
        with open('log.txt', 'a') as f:
            f.write(f"{e} url: {url}\n")
        await channel.send('發生錯誤，再試一次', file=discord.File('./image/broken_face.png'))

@bot.hybrid_command(name='kirito', description='與桐人對話')
@app_commands.guilds(discord.Object(id=SERVER_ID))
async def kirito(ctx: commands.Context, say: str):
    try:
        if len(say) == 0:
            return
        await ctx.send(f"{ctx.author.name}: {say}")
        thinking = await ctx.send('大腦在星爆', file=discord.File('./image/starburst.gif'))
        response = await bot.generate_response(say, 1)
        await thinking.delete()
        await ctx.send(response)
    except Exception as e:
        with open('log.txt', 'a') as f:
            f.write(f"{e}\n")
        await thinking.delete()
        await ctx.send('桐人停止了思考，再試一次', file=discord.File('./image/broken_face.png'))
    
if __name__ == '__main__':
    try:
        # keep_alive()
        bot.run(TOKEN)
    except discord.errors.HTTPException:
        print("blocked by Discord, restarting...")
        os.system('kill 1')
        os.system("python restarter.py")