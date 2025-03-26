from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent, MessageSegment, Message
from nonebot.plugin.on import on_command
from nonebot.params import CommandArg
from nonebot.log import logger
from nonebot import require
from nonebot.plugin import PluginMetadata
from datetime import datetime
from typing import Union
from .config import Config
from .utils import update_anime_database,fetch_bangumi_data,get_weekly_schedule,save_daily_dramas,anime_render,get_drama_detail
scheduler = require("nonebot_plugin_apscheduler").scheduler


__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-animepush",
    description="幻歆",
    usage=(
        "每日番剧数据\n",
        "并将数据渲染为图片发送\n",
        "命令：/今日番剧\n",
        "命令：/本周番剧\n",
        "命令：/番剧详情[番剧id]\n",
        "命令：/更新番剧数据"
    ),
    type="application",
    homepage="https://github.com/none",
    config=Config,
    supported_adapters={
        "~onebot.v11"
    },
)

fanju = on_command("今日番剧", aliases={"今日番剧"}, priority=5)
fanju_week = on_command("本周番剧", aliases={"本周番剧"}, priority=5)
fanju_update = on_command("更新番剧数据", aliases={"更新番剧数据"}, priority=5)
fanju_detail = on_command("番剧详情", aliases={"番剧详情"}, priority=5)

@fanju_detail.handle()
async def _(event: Union[GroupMessageEvent,PrivateMessageEvent], args: Message = CommandArg()):
    drama_id = args.extract_plain_text().strip()
    if not drama_id:
        await fanju_detail.finish("请输入番剧id")
    drama = await get_drama_detail(drama_id)
    info = f"番剧id:{drama['id']}\n番剧名称:{drama['title']}\n番剧状态:{drama['status']}\n番剧开始时间:{drama['begain_day']}\n番剧更新时间:{drama['update_day']}\n番剧结束时间:{drama['end_day']}\n番剧播放网站:{drama['playsite']}\n番剧图片:{drama['image']}"
    if drama:
        await fanju_detail.finish(info)
    else:
        await fanju_detail.finish("番剧数据获取失败")

@fanju_update.handle()
async def _(event: Union[GroupMessageEvent,PrivateMessageEvent]):
    data = fetch_bangumi_data()
    now = datetime.now()
    week,stats = await update_anime_database(data=data,update_all=False)
    if week and stats:
        logger.success(f"【{now}】:番剧数据更新成功")
        weekly_schedule, stats = await get_weekly_schedule(data)
        if await save_daily_dramas(weekly_schedule):
            logger.debug("成功保存本周番剧数据到数据库")
        await fanju_update.finish("番剧数据更新成功")
    else:
        await fanju_update.finish("番剧数据更新失败")

@fanju_week.handle()
async def _(event: Union[GroupMessageEvent,PrivateMessageEvent], args: Message = CommandArg()):
    _columns = args.extract_plain_text().strip()
    try:
        columns = int(_columns)
    except ValueError:
        columns = 1
    image,weekly_schedule,stats = await anime_render(columns=columns)
    if image:
        await fanju.finish((MessageSegment.image(file=f"file:///{str(image)}")))
    else:
        await fanju.finish("番剧数据获取失败")

@fanju.handle()
async def _(event: Union[GroupMessageEvent,PrivateMessageEvent], args: Message = CommandArg()):
    today = datetime.now().date()
    weekday = today.weekday()
    _columns = args.extract_plain_text().strip()
    try:
        columns = int(_columns)
    except ValueError:
        columns = 1
    image,weekly_schedule,stats = await anime_render(day_week=weekday,columns=columns)
    if image:
        await fanju.finish((MessageSegment.image(file=f"file:///{str(image)}")))
    else:
        await fanju.finish("番剧数据获取失败")



@scheduler.scheduled_job("interval", hours=24)
async def update_drama():
    data = fetch_bangumi_data()
    now = datetime.datetime.now()
    week,stats = await update_anime_database(data=data,update_all=False)
    if week and stats:
        logger.success(f"【{now}】:番剧数据更新成功")
        weekly_schedule, stats = await get_weekly_schedule(data)
        if await save_daily_dramas(weekly_schedule):
            logger.debug("成功保存本周番剧数据到数据库")