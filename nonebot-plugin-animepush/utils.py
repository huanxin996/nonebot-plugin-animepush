import requests,time
from tortoise.expressions import Q
from .model import Todaydrama,Dramastatus
from .config import config
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional, Dict, Any
from nonebot.log import logger
from nonebot import require
from pathlib import Path
require("nonebot_plugin_htmlrender")
from nonebot_plugin_htmlrender import template_to_pic
import nonebot_plugin_localstore as store



def fetch_bangumi_data():
    """获取 bangumi-data 数据"""
    url = "https://unpkg.com/bangumi-data@0.3.165/dist/data.json"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"获取数据失败: {response.status_code}")
    return response.json()

def get_ganzhi_date(date=None):
    """将公历日期转换为干支纪年"""
    if date is None:
        date = datetime.now()
    celestial_stems = '甲乙丙丁戊己庚辛壬癸'
    terrestrial_branches = '子丑寅卯辰巳午未申酉戌亥'
    month_branches = '寅卯辰巳午未申酉戌亥子丑'
    year = date.year
    year_stem = celestial_stems[(year - 4) % 10]
    year_branch = terrestrial_branches[(year - 4) % 12]
    year_ganzhi = f"{year_stem}{year_branch}年"
    base_year = 1984
    year_stem_index = (year - 4) % 10
    month_stem_index = (year_stem_index * 2 + date.month) % 10
    month_stem = celestial_stems[month_stem_index]
    month_branch = month_branches[date.month - 1]
    month_ganzhi = f"{month_stem}{month_branch}月"
    base_date = datetime(1984, 1, 1)
    days = (date.date() - base_date.date()).days
    day_stem = celestial_stems[days % 10]
    day_branch = terrestrial_branches[days % 12]
    day_ganzhi = f"{day_stem}{day_branch}日"
    return year_ganzhi, month_ganzhi, day_ganzhi

def parse_broadcast_time(broadcast, base_date=None):
    """解析播放时间格式为datetime对象"""
    if not broadcast:
        logger.debug("播放时间格式为空，跳过处理")
        return None
    if base_date is None:
        today = datetime.now()
        base_date = today - timedelta(days=today.weekday())
    try:
        if isinstance(broadcast, dict):
            weekday = broadcast.get('weekday')
            time_str = broadcast.get('time', '')
            if weekday is not None and time_str:
                try:
                    weekday = (weekday + 6) % 7
                    target_date = base_date + timedelta(days=weekday)
                    if ':' in time_str:
                        hour, minute = map(int, time_str.split(':'))
                        return target_date.replace(hour=hour, minute=minute)
                    else:
                        logger.debug(f"无效的时间格式: {time_str}，使用默认时间00:00")
                        return target_date
                except (ValueError, TypeError) as e:
                    logger.warning(f"解析时间出错: {time_str}, {str(e)}")
                    return target_date
        elif isinstance(broadcast, str):
            if not broadcast.strip():
                logger.debug("播放时间格式为空，跳过处理")
                return None 
            try:
                if '/' in broadcast:
                    date_str = broadcast.split('/')[1]
                else:
                    date_str = broadcast
                date_str = date_str.replace('Z', '+00:00')
                if 'T' not in date_str:
                    date_str += 'T00:00:00+00:00'
                return datetime.fromisoformat(date_str) 
            except (IndexError, ValueError) as e:
                logger.warning(f"无法解析日期字符串: {broadcast}, {str(e)}")
                return None    
    except Exception as e:
        logger.error(f"解析播放时间时发生错误: {str(e)}")
        return None  
    return None

async def check_drama_status(bgm_id):
    """检查动画在数据库中的状态"""
    try:
        drama = await Dramastatus.get_or_none(id=bgm_id)
        if drama is None:
            logger.debug(f"数据库中未找到ID为 {bgm_id} 的动画")
            return False, False, None 
        is_ended = drama.status == '已完结'
        return True, is_ended, drama
    except Exception as e:
        logger.error(f"检查动画状态时发生错误: {str(e)}")
        return False, False, None

def get_anime_image_from_bangumi(bgm_id, max_retries=2):
    """从 Bangumi 获取番剧图片"""
    retry_count = 0
    while retry_count < max_retries:
        try:
            search_url = f"https://api.bgm.tv/v0/subjects/{bgm_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json'
            }
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data and 'images' in data:
                for size in ['large', 'common', 'medium', 'grid', 'small']:
                    image_url = data['images'].get(size)
                    if image_url:
                        return image_url.replace('http://', 'https://')
            print(f"未找到 ID {bgm_id} 的图片")
            return None
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count == max_retries:
                print(f"从 Bangumi 获取 ID {bgm_id} 图片失败: {str(e)}")
                return None
            print(f"第 {retry_count} 次重试获取图片...")
            time.sleep(2 ** retry_count)
        except Exception as e:
            print(f"处理 ID {bgm_id} 时发生未知错误: {str(e)}")
            return None
        time.sleep(1)
    return None

async def save_drama_status(item):
    """保存番剧状态到数据库"""
    try:
        begin = item.get('begin')
        broadcast = item.get('broadcast')
        end = item.get('end', None)
        title = item.get('title')
        titleTranslate = item.get('titleTranslate')
        sites = item.get('sites')
        bgm_id = None
        for site_info in sites:
            if site_info['site'] == 'bangumi':
                bgm_id = site_info['id']
                break    
        if not bgm_id:
            logger.warning(f"未找到 bangumi ID: {title}")
            return False  
        status, is_end, drama = await check_drama_status(bgm_id)
        existing_drama = await Dramastatus.get_or_none(id=bgm_id)
        if status and is_end:
            logger.debug(f"{title} 已完结，无需更新")
            return True      
        if not all([begin, title, sites]):
            logger.warning(f"数据不完整: {bgm_id}")
            return False
        title = titleTranslate.get('zh-Hans', [None])[0] or title
        if not title:
            logger.warning(f"无法获取标题: {bgm_id}")
            return False
        try:
            begin_date = parse_broadcast_time(begin)
            if not begin_date:
                logger.warning(f"无法解析开播时间: {begin}")
                return False    
            end_date = parse_broadcast_time(end) if end else None
            broadcast_time = parse_broadcast_time(broadcast) if broadcast else None
            if not broadcast_time:
                broadcast_time = begin_date
                logger.debug(f"使用开播时间作为更新时间: {title}")
        except ValueError as e:
            logger.error(f"日期格式错误: {str(e)}")
            return False
        update_data = {
            'status': '连载中' if not end else '已完结',
            'title': title,
            'begain_day': begin_date,
            'update_day': broadcast_time,
            'end_day': end_date,
            'playsite': [site.get('site') for site in sites],
            'raw_json': item,
            'update_time': datetime.now()
        }
        if existing_drama:
            need_update = False
            if existing_drama.status != update_data['status']:
                need_update = True
                logger.debug(f"状态变化: {existing_drama.status} -> {update_data['status']}")  
            if existing_drama.end_day != update_data['end_day']:
                need_update = True
                logger.debug(f"完结时间变化: {existing_drama.end_day} -> {update_data['end_day']}")  
            if existing_drama.update_day != update_data['update_day']:
                need_update = True
                logger.debug(f"更新时间变化: {existing_drama.update_day} -> {update_data['update_day']}")
            if set(existing_drama.playsite) != set(update_data['playsite']):
                need_update = True
                logger.debug(f"播放站点变化: {existing_drama.playsite} -> {update_data['playsite']}")
            if need_update:
                image = get_anime_image_from_bangumi(bgm_id)
                if image:
                    update_data['image_header'] = image
                else:
                    update_data['image_header'] = existing_drama.image_header
                for key, value in update_data.items():
                    setattr(existing_drama, key, value)
                await existing_drama.save()
                logger.debug(f"更新番剧: {title}")
                return True
            else:
                logger.debug(f"番剧无需更新: {title}")
                return False
        else:
            image = get_anime_image_from_bangumi(bgm_id)
            update_data['image_header'] = image if image else ''
            await Dramastatus.create(id=bgm_id, **update_data)
            logger.debug(f"新增番剧: {title}")
            return True
    except Exception as e:
        logger.error(f"保存番剧数据失败: {str(e)}")
        return False

async def update_anime_database(data, update_all=False):
    """更新番剧数据库"""
    if not data or 'items' not in data:
        logger.warning("无有效数据可更新")
        return 0 
    try:
        logger.info("开始更新数据库...")
        update_count = 0
        today = datetime.now()  
        for item in data['items']:
            if item.get('type') != 'tv':
                continue      
            begin_date = parse_broadcast_time(item.get('begin'))
            end_date = parse_broadcast_time(item.get('end')) if item.get('end') else None     
            if not begin_date:
                continue
            is_ended = end_date and end_date.date() <= today.date()
            should_update = update_all or not is_ended
            if should_update:
                if await save_drama_status(item):
                    update_count += 1
                    logger.debug(f"更新动画: {item.get('title')} {'[已完结]' if is_ended else '[连载中]'}")
        logger.info(f"数据库更新完成，更新了 {update_count} 条记录")
        return update_count
    except Exception as e:
        logger.error(f"更新数据库失败: {str(e)}")
        return 0

async def get_weekly_schedule(data=None):
    """获取本周动画时间表"""
    weekly_anime = defaultdict(list)
    stats = {'updating': 0, 'ended': 0}
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    logger.debug(f"获取 {monday.strftime('%Y-%m-%d')} 到 {sunday.strftime('%Y-%m-%d')} 的动画数据")
    try:
        dramas = await Dramastatus.filter(
            Q(begain_day__lte=sunday),
            Q(end_day__isnull=True) | Q(end_day__gte=monday)
        )
        def add_anime_to_schedule(drama, update_time):
            """添加动画到时间表"""
            if not update_time:
                update_time = drama.begain_day
                if not update_time:
                    return False     
            weekday_name = update_time.strftime('%A')
            is_ended = drama.end_day and drama.end_day.date() <= today.date()
            ends_this_week = drama.end_day and drama.end_day.date() <= sunday.date()
            if is_ended:
                stats['ended'] += 1
            else:
                stats['updating'] += 1   
            anime_info = {
                'id': drama.id,
                'title': drama.title,
                'begin': drama.begain_day.strftime('%Y-%m-%d'),
                'update': update_time.strftime('%Y-%m-%d'),
                'update_time': update_time.strftime('%H:%M'),
                'sites': drama.playsite,
                'status': '本周完结' if ends_this_week else '连载中',
                'image': drama.image_header if drama.image_header else None
            }
            weekly_anime[weekday_name].append(anime_info)
            logger.debug(f"添加动画: {drama.title} -> {weekday_name} [{anime_info['status']}]")
            return True
        for drama in dramas:
            add_anime_to_schedule(drama, drama.update_day)
        if not any(weekly_anime.values()) and data and 'items' in data:
            logger.debug("数据库中无数据，尝试从API获取")
            for item in data['items']:
                if item.get('type') != 'tv':
                    continue
                if await save_drama_status(item):
                    bgm_id = None
                    for site_info in item['sites']:
                        if site_info['site'] == 'bangumi':
                            bgm_id = site_info['id']
                            break   
                    if bgm_id:
                        drama = await Dramastatus.get_or_none(id=bgm_id)
                        if drama:
                            broadcast_time = parse_broadcast_time(item.get('broadcast'))
                            add_anime_to_schedule(drama, broadcast_time)
        if await save_daily_dramas(weekly_anime):
            logger.debug("成功保存本周番剧数据到数据库")     
            return weekly_anime, stats
    except Exception as e:
        logger.error(f"获取每周动画数据失败: {str(e)}")
        return defaultdict(list), {'updating': 0, 'ended': 0}

async def save_daily_dramas(weekly_schedule):
    """保存每日番剧数据到数据库"""
    try:
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)
        await Todaydrama.filter(date__lt=week_ago).delete()
        logger.debug("已清理一周前的番剧数据")
        weekdays = {
            'Monday': 0,
            'Tuesday': 1, 
            'Wednesday': 2,
            'Thursday': 3,
            'Friday': 4,
            'Saturday': 5,
            'Sunday': 6
        }
        monday = today - timedelta(days=today.weekday())
        for weekday, anime_list in weekly_schedule.items():
            if not anime_list:
                continue
            day_offset = weekdays.get(weekday, 0)
            target_date = monday + timedelta(days=day_offset)
            drama_data = []
            for anime in anime_list:
                time_parts = anime['update_time'].split(':')[:2]
                update_time = ':'.join(time_parts)
                drama_info = {
                    'id': anime['id'],
                    'title': anime['title'],
                    'status': anime['status'],
                    'update_time': update_time,  # 只包含小时和分钟
                    'sites': anime['sites'],
                    'image': anime['image']
                }
                drama_data.append(drama_info)
            await Todaydrama.update_or_create(
                date=target_date,
                defaults={
                    'drama_list': drama_data,
                    'update_time': datetime.now()
                }
            )
            logger.debug(f"已保存 {target_date.strftime('%Y-%m-%d')} 的番剧数据: {len(drama_data)}部")
        return True 
    except Exception as e:
        logger.error(f"保存每日番剧数据失败: {str(e)}")
        return False

async def generate_anime_image(
    template_data: Dict[str, Any],
    day_week: Optional[int] = None,
    force_update: bool = False,
    columns: int = 1
) -> Optional[Path]:
    """生成动画时间表图片"""
    try:
        current_dir = Path(__file__).parent
        template_path = current_dir / "templates"
        fonts_path = template_path / "fonts"
        
        if not fonts_path.exists() or not any(fonts_path.iterdir()):
            fonts_path.mkdir(parents=True)
            template_path.mkdir(parents=True)
            logger.debug(f"创建字体目录: {fonts_path}, 模板目录: {template_path}")
        
        if not template_path.exists():
            logger.error(f"模板文件不存在: {template_path}")
            return None
        font_files = {
            'medium': f"fonts/{config.fanju_fonts_medium}",
            'bold': f"fonts/{config.fanju_fonts_bold}"
        }
        for font_type, rel_path in font_files.items():
            abs_path = template_path / rel_path
            if not abs_path.exists():
                logger.warning(f"字体文件不存在: {abs_path}")
                font_files[font_type] = None
        today = datetime.now().date()
        save_dir = store.get_cache_dir("fanju")
        if not save_dir.exists():
            save_dir.mkdir(parents=True)
        file_name = f"anime_schedule_{today.strftime('%Y%m%d')}"
        if day_week is not None:
            file_name += f"_day{day_week}"
        file_name += ".jpg"
        image_path = save_dir / file_name
        if not force_update and image_path.exists():
            logger.debug(f"找到缓存的图片: {image_path}")
            return image_path
        week_ago = today - timedelta(days=7)
        for old_file in save_dir.glob("anime_schedule_*.jpg"):
            file_date_str = old_file.stem.split('_')[2]
            try:
                file_date = datetime.strptime(file_date_str, '%Y%m%d').date()
                if file_date < week_ago:
                    old_file.unlink()
                    logger.debug(f"删除过期图片: {old_file}")
            except ValueError:
                continue
        weekday_pairs = []
        for i in range(len(template_data['weekdays'])):
            weekday_pairs.append({
                'en': template_data['weekdays'][i],
                'zh': template_data['weekdays_zh'][i]
            })
        template_data['weekday_pairs'] = weekday_pairs
        template_data.update({
            'footer_info': '数据来源于 Bangumi API',
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': config.version,
            'columns': columns,
            'fonts': font_files,
            'copyright': 'nonebot-plugin-animepush    © 2025 huanxin996. All rights reserved.'
        })
        viewport_width = 800 if columns == 1 else 1800
        viewport_height = 1200 if columns == 1 else 1000
        image_bytes = await template_to_pic(
            template_path=template_path,
            template_name="anime_schedule.html",
            templates=template_data,
            pages={
                "viewport": {"width": viewport_width, "height": viewport_height}
            },
            wait=config.fanju_image_wait,
            type="jpeg",
            quality=config.fanju_image_quality
        )
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        logger.debug(f"生成新的图片: {image_path}")
        return image_path
    except Exception as e:
        logger.error(f"生成图片失败: {str(e)}")
        return None

async def anime_render(force_update=False, update_all=False, day_week:int = None, columns:int = 1):
    """渲染动画数据"""
    try:
        year_gz, month_gz, day_gz = get_ganzhi_date()
        today_date = f"📅: {year_gz} {month_gz} {day_gz}"
        logger.debug("------------------------")
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekdays_zh = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        weekly_schedule = defaultdict(list)
        stats = {'updating': 0, 'ended': 0}
        if not force_update:
            for i, weekday in enumerate(weekdays):
                target_date = monday + timedelta(days=i)
                drama_data = await Todaydrama.get_or_none(date=target_date)
                if drama_data and drama_data.drama_list:
                    weekly_schedule[weekday] = drama_data.drama_list
                    for anime in drama_data.drama_list:
                        if anime['status'] == '本周完结':
                            stats['ended'] += 1
                        else:
                            stats['updating'] += 1
            if any(weekly_schedule.values()):
                logger.debug("从数据库获取到本周动画数据")
            else:
                logger.debug("数据库中无数据，尝试从API获取")
                force_update = True
        if force_update:
            logger.debug("正在从API获取最新数据...")
            data = fetch_bangumi_data()
            logger.debug("数据获取成功！")
            logger.debug("------------------------")
            update_count = await update_anime_database(data, update_all=update_all)
            logger.debug(f"数据库更新完成，更新了 {update_count} 条记录")
            logger.debug("------------------------")
            weekly_schedule, stats = await get_weekly_schedule(data)
        if day_week is not None:
            if 0 <= day_week <= 6:
                target_day = weekdays[day_week]
                target_anime_list = weekly_schedule.get(target_day, [])
                filtered_schedule = {target_day: target_anime_list}
                weekly_schedule = filtered_schedule
                stats = {'updating': 0, 'ended': 0}
                for anime in target_anime_list:
                    if anime['status'] == '本周完结':
                        stats['ended'] += 1
                    else:
                        stats['updating'] += 1
            else:
                logger.warning(f"无效的星期参数: {day_week}，应为0-6")
        total_anime = sum(len(anime) for anime in weekly_schedule.values())
        if day_week is not None and 0 <= day_week <= 6:
            target_day_zh = weekdays_zh[day_week]
            logger.debug(f"- {target_day_zh}更新动画: {total_anime} 部")
        else:
            logger.debug(f"- 本周更新动画: {total_anime} 部")
        logger.debug(f"- 连载中: {stats['updating']} 部")
        logger.debug(f"- 已完结: {stats['ended']} 部")
        template_data = {
            'today_date': today_date,
            'weekly_schedule': weekly_schedule,
            'stats': stats,
            'total_anime': total_anime,
            'weekdays': weekdays,
            'weekdays_zh': weekdays_zh,
            'day_week': day_week
        }
        image_path = await generate_anime_image(
            template_data=template_data,
            day_week=day_week,
            force_update=force_update,
            columns=columns
        )
        logger.debug(f"图片已保存到: {image_path}")
        return image_path, weekly_schedule, stats
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")
        return None, None


async def get_drama_detail(drama_id):
    """获取番剧详情"""
    try:
        drama = await Dramastatus.get_or_none(id=drama_id)
        if drama:
            drama_data = {
                'id': drama.id,
                'title': drama.title,
                'status': drama.status,
                'begain_day': drama.begain_day.strftime('%Y-%m-%d') if drama.begain_day else None,
                'update_day': drama.update_day.strftime('%Y-%m-%d %H:%M') if drama.update_day else None,
                'end_day': drama.end_day.strftime('%Y-%m-%d') if drama.end_day else None,
                'playsite': drama.playsite,
                'image': drama.image_header
            }
            return drama_data
        else:
            return None
    except Exception as e:
        logger.error(f"获取番剧详情失败: {str(e)}")
        return None