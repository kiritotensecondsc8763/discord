import os

MODE = 'test'

server_id = {
    'test': 1057271413540671690,
    'public': 937172350183563275,
}
fashion_channel = {
    'test': 1057271414257885286,
    'public': 1060913729023262832,
}
treasure_channel = {
    'test': 1057271414257885286,
    'public': 949541903240675328
}

TOKEN = os.environ.get(f"DISCORD_BOT_TOKEN_{MODE.upper()}")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERVER_ID = server_id[MODE]
FASHION_CHANNEL = fashion_channel[MODE]
TREASURE_CHANNEL = treasure_channel[MODE]
DB = 'db' if MODE == 'public' else 'db_test'

HEROES = [
    '潔西卡到門', '瓊稻穗宮媛', '阿修羅霸凰槍',
    '鏡面彼岸', '恆月三途', '掰開姐姐的花瓣', '掰開姊姊的花瓣', 
    '百華月詠', '柳生九兵衛', '結野', '百音', 
    '斯庫爾德', '桑夏',
    '安潔露可', 'ArutoRiese', '艾克瑟蓮',
]

TREASURE_KEYWORDS = ['輕薄', '銳利', '穩定', '完整', '剛硬', '光滑', '特殊', '附魔', '卷軸', '未知', '鬥爭', '封印', '高級', '項鍊']
BLOCK_KEYWORDS = ['防', '具', '60', '40']

SCROLLS = [
    '殘酷的', '渾沌的', '正義的', '不義的', '怨恨', '信念', '審判', '判刑',
    '冷靜的', '無情的', '回憶的', '進擊', '束縛', '遠征',
    '悲痛的', '啜泣的', '反覆的', '狂暴', '靈魂', '回音',
    '高尚的', '無限的', '時間的', '悲嘆', '結界', '烙印',
    '扭曲的', '深刻的', '神秘', '暴怒', '願望',
    '激烈的', '封印的', '瘋狂', '真實',
    '強烈的', '隱隱約約的',
    '追蹤者的', '亡者的',
    '平穩的', '堅決的', '擺好姿勢的', '冥想的', '決意的', '幽靜的',
    '爆裂', '疾走', '熱烈', '散步',
]

WAKING_STONES = ['傷害增加12%', 'SP消耗減少80', '冷卻時間大幅減少24秒', '冷卻時間減少6秒', '擊倒值增加12%', '耐力消耗減少6']

GLASS_BOTTLE_LEVELS = ['80', '100', '110']

TREASURES = ['未知的黃金手環', '未知的純銀手環', '璀璨的貓咪項鍊', '特殊戰役:附魔袋', '高級強化藥水']
[TREASURES.append(f"{scroll}附魔卷軸") for scroll in SCROLLS]
[TREASURES.append(f"覺醒石：{stone}") for stone in WAKING_STONES]
[TREASURES.append(f"未知的玻璃瓶({level}級)") for level in GLASS_BOTTLE_LEVELS]
