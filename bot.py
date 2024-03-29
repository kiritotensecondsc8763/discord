import discord
import requests
import time
import random
import imghdr
import os
# import openai
# import stopit
import pytesseract
import cv2
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
        self.write_log(error)
        await ctx.send('發生錯誤，再試一次', file=discord.File(f"{IMAGE_DIR}/broken_face.png"))

    def write_log(self, message):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(f"{LOG_DIR}/log.txt", 'a', encoding='utf-8') as f:
            f.write(f"{current_time} - {message}\n")

    async def get_fashion(self):
        while True:
            random.seed(int(time.time()))
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

        srcs = [img['src'] for img in imgs if img['src'] != 'https://nstatic.dcinside.com/dc/w/images/w_webp.png']
        if not srcs:
            return False

        src = random.choice(srcs)
        src = urlparse(src)
        src = src._replace(netloc=src.netloc.replace(src.hostname, 'dcimg4.dcinside.co.kr')).geturl()
        response = requests.get(src, headers=headers, stream=True)
        extension = imghdr.what(None, response.content)
        if not extension:
            return False

        base_name = 'fashion'
        file_path = os.path.join(DOWNLOAD_DIR, f"{base_name}.{extension}")

        with open(file_path, 'wb') as f:
            f.write(response.content)

        file_size = os.path.getsize(file_path)
        print(f"Size: {self.format_file_size(file_size)}")
        if file_size < 10000:
            os.remove(file_path)
            return False

        if extension == 'webp' and file_size >= 3000000:
            max_size = (1920, 1080)
            image = Image.open(file_path).convert('RGB')
            file_path_png = os.path.join(DOWNLOAD_DIR, f"{base_name}.png")
            image.save(file_path_png, 'png')

            os.remove(file_path)
            file_path = file_path_png

            file_size = os.path.getsize(file_path)
            print(f"png resize: {self.format_file_size(file_size)}")

        elif extension == 'gif' and file_size >= 8000000:
            max_size = (320, 240)
            image = Image.open(file_path)
            frames = ImageSequence.Iterator(image)
            frames = self.thumbnails(frames, max_size)

            om = next(frames)
            om.info = image.info
            file_path_gif = os.path.join(DOWNLOAD_DIR, f"{base_name}.gif")
            om.save(file_path_gif, save_all=True, append_images=list(frames))

            os.remove(file_path)
            file_path = file_path_gif

            file_size = os.path.getsize(file_path)
            print(f"gif resize: {self.format_file_size(file_size)}")

        return file_path

    def format_file_size(self, size):
        size = size / 1024
        if size < 1024:
            return f"{size:.2f} KB"
        else:
            size = size / 1024
            return f"{size:.2f} MB"

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
            self.write_log(f"url: {url}\n{e}")
            await channel.send('發生錯誤，再試一次', file=discord.File(f"{IMAGE_DIR}/broken_face.png"))

    def super_resolution(self, image, m):
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(f"{SR_MODEL_DIR}/LapSRN_x{m}.pb")
        sr.setModel("lapsrn", m)
        return sr.upsample(image)

    def gray(self, image):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    def thresh_binary(self, image):
        ret, image = cv2.threshold(image, 85, 255, cv2.THRESH_TOZERO)
        return image

    def sharpen(self, filename):
        image = Image.open(filename)
        output = image.filter(ImageFilter.SHARPEN)
        output.save(filename)

    def setDPI(self, filename):
        image = Image.open(filename)
        image.save(filename, dpi=(300,300))

    async def download_image(self, index, url):
        accepted_extensions = ['.jpg', '.jpeg', '.png']
        parsed_url = urlparse(url)
        extension = splitext(basename(parsed_url.path))[1]
        if extension not in accepted_extensions:
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                filename = f"t{index}{extension}"
                if not os.path.exists(DOWNLOAD_DIR):
                    os.makedirs(DOWNLOAD_DIR)
                with open(f"{DOWNLOAD_DIR}/{filename}", 'wb') as f:
                    f.write(await response.content.read())
        return filename

    async def parse_attachments(self, attachments):
        tasks = [asyncio.create_task(self.download_image(index, attachment.url)) for index, attachment in enumerate(attachments)]
        results = await asyncio.wait(tasks)

        filenames = []
        [filenames.append(result.result()) for result in results[0] if result.result() is not None]
            
        return filenames

    def parse_image(self, filename):
        filename = f"{DOWNLOAD_DIR}/{filename}"

        image = cv2.imread(filename)
        image = self.super_resolution(image, 2)
        image = self.gray(image)
        image = cv2.medianBlur(image, 1)
        # blur = cv2.GaussianBlur(image, (0, 0), 50)
        # image = cv2.addWeighted(image, 1.5, blur, -0.5, 0)
        image = self.thresh_binary(image)
        cv2.imwrite(filename, image)
        self.sharpen(filename)
        self.setDPI(filename)

        image = Image.open(filename)
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 6')

        if os.path.exists(filename):
            os.remove(filename)

        return text

    async def parse_texts(self, texts, message):
        special_characters = [' ', '[SYSTEM]', '[', ']']
        records = {}
        treasure_records = {}

        for text in texts:
            rows = text.replace(' ', '').replace('獲得了', '得').replace('獲得', '得').split('\n')

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
                    type = 'treasure'

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
                    if score > 50:
                        item = closest_item

                    if any(t in row for t in TREASURE_KEYWORDS):
                        if not any(b in row for b in BLOCK_KEYWORDS):
                            if name not in treasure_records:
                                treasure_records[name] = []
                            if item == '高級強化藥水2個' or item == '2個高級強化藥水':
                                treasure_records[name] += [{'type': type, 'item': '高級強化藥水'}] * 2
                            else:
                                treasure_records[name].append({'type': type, 'item': item})

                    if name not in records:
                        records[name] = []
                    records[name].append({'type': type, 'item': item})
                    
        if len(treasure_records) > 0:
            records = treasure_records
            self.insert_data(treasure_records)

        if len(records) == 0 or (len(records) > 1 and len(treasure_records) == 0):
            return

        await message.channel.send(file=discord.File(f"{IMAGE_DIR}/congratulations.png"))
        await message.channel.send(self.generate_congratulations(records))

    def insert_data(self, records):
        connection = sqlite3.connect(os.path.join(DB_DIR, DB))

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

    def generate_congratulations(self, records):
        congratulations = ''
        if len(records) > 1:
            congratulations += '【恭喜以下英雄】\n\n'
        for name, record in records.items():
            if len(records) == 1 and name == '未知':
                congratulations += '不知道你是誰，恭喜你獲得'
            elif len(records) == 1:
                congratulations += f"恭喜【{name}】獲得"
            elif len(records) > 1:
                congratulations += f"【{name}】獲得"

            organized_records = {}
            for item in record:
                if item['type'] != 'treasure':
                    continue
                if item['item'] not in organized_records:
                    organized_records[item['item']] = 1
                else:
                    organized_records[item['item']] += 1

            for item in record:
                if item['type'] == 'enhance':
                    congratulations = congratulations[:-2]
                    congratulations += f"成功強化至【{item['item']}】"
                elif item['type'] == 'capsule':
                    congratulations = congratulations[:-2]
                    congratulations += f"在【{item['capsule']}】獲得【{item['item']}】"
                elif item['type'] == 'treasure':
                    for item, count in organized_records.items():
                        count = f" × {count}" if count > 1 else ''
                        congratulations += f"【{item}{count}】"
                    break
            congratulations += '\n'
        return congratulations

    @tasks.loop(seconds=1)
    async def show_treasure_statistics(self, start_date:str="", end_date:str=""):
        is_auto = True if start_date == "" and end_date == "" else False
        if is_auto:
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
            title = '本週戰利品統計'
        else:
            title = '戰利品查詢結果'

        connection = sqlite3.connect(os.path.join(DB_DIR, DB))
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

        embed = discord.Embed(title=title, description=f"{start_date} 09:00 ~ {end_date} 09:00", color=0xFDC344)
    
        for name, items in statistics.items():
            embed.add_field(name="", value="\n")
            value = ''
            for item, count in items.items():
                value += f"{item} × {count}\n"
            embed.add_field(name=f"【{name}】", value=value, inline=False)

        if is_auto:
            await self.get_channel(TREASURE_CHANNEL).send(embed=embed)
        else:
            return embed