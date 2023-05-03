import discord
import requests
import random
import imghdr
import os
import openai
import stopit
import pytesseract
import cv2
import numpy as np
import sqlite3
import asyncio
import aiohttp
from discord.ext import commands, tasks
from fashion_list import items, blocks
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urlparse
from PIL import Image, ImageSequence, ImageFilter
from datetime import date, datetime, timedelta, timezone
from os.path import splitext, basename
from cv2 import dnn_superres
from fuzzywuzzy import fuzz, process
from settings import *


class Kirito(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, case_insensitive=True)

    async def setup_hook(self):
        await self.tree.sync(guild=discord.Object(id=SERVER_ID))
        print(f"Synced slash commands for {self.user}")

    async def on_command_error(self, ctx, error):
        with open('log.txt', 'a') as f:
            f.write(f"{error}\n")
        await ctx.send('發生錯誤，再試一次', file=discord.File('./image/broken_face.png'))

    async def get_fashion(self):
        while True:
            item = random.choice(items)
            url = item['url']
            
            if item['type'] == 'main':
                url = await self.get_detail_url(url)
                if not url:
                    continue 
            file_path = await self.get_image(url)

            if file_path != False:
                break
        
        return item['name'], file_path, url

    async def get_detail_url(self, url):
        headers = {'user-agent': UserAgent().random}
        with requests.get(url, headers=headers) as response: 
            soup = BeautifulSoup(response.text, 'lxml')
            detail_urls = soup.select('a[class="lnk"]')
            if len(detail_urls) == 0:
                return False

        while True:
            detail_url = random.choice(detail_urls)['href']
            if detail_url in blocks:
                continue
            return detail_url

    async def get_image(self, url):
        headers = {'user-agent': UserAgent().random}
        with requests.get(url, headers=headers) as response: 
            soup = BeautifulSoup(response.text, 'lxml')
            imgs = soup.select('div[class="write_div"] img')
            if len(imgs) == 0:
                return False

        srcs = []
        for img in imgs:
            if img['src'] == 'https://nstatic.dcinside.com/dc/w/images/w_webp.png':
                continue
            srcs.append(img['src'])
        if len(srcs) == 0:
            return False

        src = random.choice(srcs)
        src = urlparse(src)
        src = src._replace(netloc=src.netloc.replace(src.hostname, 'dcimg4.dcinside.co.kr')).geturl()
        response = requests.get(src, headers=headers, stream=True)
        base_name = 'fashion'

        with open(base_name, 'wb') as f:
            f.write(response.content)

        file_size = os.path.getsize(base_name)
        print(f"size: {file_size}")
        if file_size < 10000:
            os.remove(base_name)
            return False

        extension = imghdr.what(base_name)
        if extension == None:
            os.remove(base_name)
            return False
            
        file_name = f"{base_name}.{extension}"
        if os.path.isfile(file_name):
            os.remove(file_name)
        os.rename(base_name, file_name)

        if extension == 'webp' and file_size >= 3000000:
            file_name = f"{base_name}.{extension}"
            max_size = 1920, 1080
            image = Image.open(file_name).convert('RGB')
            file_name = f"{base_name}.png"
            image.save(file_name, 'png')

            file_size = os.path.getsize(file_name)
            print(f"png resize: {file_size}")

            # image = Image.open(file_name)
            # file_name = f"{base_name}.gif"
            # image.info.pop('background', None)
            # if os.path.isfile(file_name):
            #     os.remove(file_name)
            # image.save(file_name, 'gif', save_all=True)

        elif extension == 'gif' and file_size >= 8000000:
            max_size = 320, 240
            image = Image.open(file_name)
            frames = ImageSequence.Iterator(image)
            frames = self.thumbnails(frames, max_size)

            om = next(frames)
            om.info = image.info
            om.save(file_name, save_all=True, append_images=list(frames))

            file_size = os.path.getsize(file_name)
            print(f"gif resize: {file_size}")

        file_path = os.path.realpath(file_name)
        return file_path

    def thumbnails(self, frames, max_size):
        for frame in frames:
            thumbnail = frame.copy()
            thumbnail.thumbnail(max_size, Image.LANCZOS)
            yield thumbnail

    async def generate_response(self, prompt, temperature):
        with stopit.ThreadingTimeout(30) as context_manager:
            completions = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=2048,
                n=1,
                stop=None,
                temperature=temperature,
            )
            text = completions['choices'][0]['text']
        if context_manager.state == context_manager.EXECUTED:
            return text
        elif context_manager.state == context_manager.TIMED_OUT:
            raise

    @tasks.loop(seconds=1)
    async def get_fashion_automatically(self):
        try:
            if datetime.now().minute % 15 != 0 or datetime.now().second != 0:
                return
            print(f"get fashion {datetime.now().hour}:{datetime.now().minute}")

            channel = self.get_channel(FASHION_CHANNEL)
            count = 0
            async for message in channel.history():
                count += 1
                if count >= 5:
                    await message.delete()

            url = 'not get fashion yet'
            name, file_path, url = await self.get_fashion()
            await channel.send(f"【{name}】", file=discord.File(file_path))
            os.remove(file_path)
        except Exception as e:
            with open('log.txt', 'a') as f:
                f.write(f"{e} url: {url}\n")
            await channel.send('發生錯誤，再試一次', file=discord.File('./image/broken_face.png'))

    def super_resolution(self, image, m):
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(f"./LapSRN_x{m}.pb")
        sr.setModel("lapsrn", m)
        return sr.upsample(image)

    def gray(self, image):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    def thresh_binary(self, image):
        blur = cv2.medianBlur(image, 1)
        result, image = cv2.threshold(blur, 127, 255, cv2.THRESH_BINARY_INV)
        return image
    
    def erode(self, image):
        kernel = np.ones((1, 1), np.uint8)
        return cv2.erode(image, kernel, iterations = 1)

    def sharpen(self, filename):
        image = Image.open(filename)
        output = image.filter(ImageFilter.SHARPEN)
        output.save(filename)

    def setDPI(self, filename):
        image = Image.open(filename)
        image.save(filename, dpi=(300,300))

    async def download_image(self, url):
        accepted_extensions = ['.jpg', '.jpeg', '.png']
        parsed_url = urlparse(url)
        extension = splitext(basename(parsed_url.path))[1]

        if extension in accepted_extensions:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    dir = "./temp"
                    filename = url.split('/')[-1]
                    if not os.path.exists(dir):
                        os.makedirs(dir)
                    with open(f"{dir}/{filename}", 'wb') as f:
                        f.write(await response.content.read())
            return filename
        
    async def create_tasks(self, message):
        tasks = [asyncio.create_task(self.download_image(attachment.url)) for attachment in message.attachments]
        results = await asyncio.wait(tasks)
    
        filenames = []
        [filenames.append(result.result()) for result in results[0] if result.result() is not None]
            
        return filenames

    async def parse_attachments(self, message):
        special_characters = [' ', '[SYSTEM]', '[', ']']
        congratulations = ''

        filenames = []
        filenames = await self.create_tasks(message)

        if len(filenames) == 0:
            return

        for filename in filenames:
            filename = f"./temp/{filename}"

            image = cv2.imread(filename)
            image = self.super_resolution(image, 2)
            image = self.gray(image)
            # blur = cv2.GaussianBlur(image, (0, 0), 50)
            # image = cv2.addWeighted(image, 1.5, blur, -0.5, 0)
            # image = self.thresh_binary(image)
            # image = self.erode(image)
            cv2.imwrite(filename, image)
            self.sharpen(filename)
            self.setDPI(filename)
            image = Image.open(filename)

            text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 6')
            rows = text.replace(' ', '').replace('獲得了', '得').replace('獲得', '得').split('\n')

            treasure_records = {}
            records = {}

            for row in rows:
                for c in special_characters:
                    row = row.replace(c, '')
                print(row)
                if '成功強化' in row and '至+' in row:
                    type = 'enhance'

                    name, item = row.split('至+')[0].split('成功強化')
                    closest_name, score = process.extractOne(name, HEROES)
                    if score > 40:
                        name = closest_name

                    if name not in records:
                        records[name] = []
                    records[name].append({'type': type, 'item': item})

                elif '得' in row and '在' in row and '包裝' in row:
                    type = 'capsule'
                    
                    first_row, item = row.split('獲得')
                    name, capsule = first_row.split('在')
                    closest_name, score = process.extractOne(name, HEROES)
                    if score > 40:
                        name = closest_name
                    
                    if name not in records:
                        records[name] = []
                    records[name].append({'type': type, 'item': item, 'capsule': capsule})

                elif '得' in row:
                    type = 'obtain'

                    name, item = row.split('。')[0].split('得')

                    closest_name, score = process.extractOne(name, HEROES)
                    if score > 40:
                        name = closest_name
                    if not name:
                        name = '未知'

                    for level in GLASS_BOTTLE_LEVELS:
                        if level in item:
                            item = f"未知的玻璃瓶({level}級)"
                            break
                    closest_item, score = process.extractOne(item, TREASURES)
                    if score > 60:
                        item = closest_item

                    if any(t in row for t in TREASURE_KEYWORDS):
                        if not any(b in row for b in BLOCK_KEYWORDS):
                            if name not in treasure_records:
                                treasure_records[name] = []
                            treasure_records[name].append({'type': type, 'item': item})

                    if name not in records:
                        records[name] = []
                    records[name].append({'type': type, 'item': item})
                    
            if len(treasure_records) > 0:
                records = treasure_records
                self.insert_data(treasure_records)
            
            for name, items in records.items():
                if name == '未知':
                    congratulations += '不知道你是誰，恭喜你獲得'
                else:
                    congratulations += f"恭喜【{name}】獲得"
                for item in items:
                    if item['type'] == 'enhance':
                        congratulations = congratulations[:-2]
                        congratulations += f"成功強化至【{item['item']}】"
                    elif item['type'] == 'capsule':
                        congratulations = congratulations[:-2]
                        congratulations += f"在【{item['capsule']}】獲得【{item['item']}】"
                    elif item['type'] == 'obtain':
                        congratulations += f"【{item['item']}】"
                congratulations += '\n'

        [os.remove(f"./temp/{filename}") for filename in filenames if os.path.exists(f"./temp/{filename}")]

        if len(records) == 0 or (len(records) > 1 and len(treasure_records) == 0):
            return

        await message.channel.send(file=discord.File('./image/congratulations.png'))
        await message.channel.send(congratulations)

    def insert_data(self, records):
        connection = sqlite3.connect(DB)

        sql =   """
                CREATE TABLE IF NOT EXISTS `treasures` (
                `id` INTEGER PRIMARY KEY AUTOINCREMENT,
                `name` VARCHAR(255) NOT NULL,
                `item` VARCHAR(255) NOT NULL,
                `time` TIMESTAMP(20) NOT NULL
                );
                """
        connection.execute(sql)

        sql = "CREATE INDEX IF NOT EXISTS `idx_name` ON `treasures` (`name`);"
        connection.execute(sql)
        
        sql = "CREATE INDEX IF NOT EXISTS `idx_time` ON `treasures` (`time`);"
        connection.execute(sql)

        sql = f"INSERT INTO treasures (`name`, `item`, `time`) VALUES "
        for name, items in records.items():
            for item in items:
                sql += f"('{name}', '{item['item']}', DATETIME('now', 'localtime')),"

        connection.execute(sql[:-1])
        connection.commit()

    @tasks.loop(seconds=1)
    async def show_treasure_statistics(self):
        now = datetime.now(tz=timezone(timedelta(hours=8)))
        weekday = now.weekday()
        current_time = now.strftime('%H:%M:%S')
        if weekday != 0 or current_time != '09:00:00':
            # print(f"weekday: {weekday}\ncurrent_time: {current_time}")
            return
        print(f"show treasure statistics {now.strftime('%Y-%m-%d %H:%M:%S')}")

        start_date = now - timedelta(days=7)
        start_date = start_date.strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')

        connection = sqlite3.connect(DB)
        connection.row_factory = sqlite3.Row
        sql =   f"""
                SELECT `name`, `item` 
                FROM `treasures` 
                WHERE `time` BETWEEN '{start_date} 09:00:00' AND '{end_date} 09:00:00'
                ORDER BY `name` DESC, `item`
                """
        records = connection.execute(sql).fetchall()
        connection.close()

        if len(records) == 0:
            return

        statistics = {}
        for record in records:
            if record['name'] not in statistics:
                statistics[record['name']] = {}
            if record['item'] in statistics[record['name']]:
                statistics[record['name']][record['item']] += 1
            else:
                statistics[record['name']][record['item']] = 1

        embed = discord.Embed(title='本週戰利品統計', description=f"{start_date} 9:00 AM ~ {end_date} 9:00 AM", color=0xFDC344)
    
        for name, items in statistics.items():
            embed.add_field(name="", value="\n")
            value = ''
            for item, count in items.items():
                value += f"{item} × {count}\n"
            embed.add_field(name=f"【{name}】", value=value, inline=False)

        await self.get_channel(TREASURE_CHANNEL).send(embed=embed)