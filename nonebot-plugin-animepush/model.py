from tortoise import fields
from tortoise.models import Model
from nonebot_plugin_tortoise_orm import add_model
add_model("nonebot_plugin_animepush.model")

class Todaydrama(Model):
    date = fields.DateField(primary_key=True)   # 日期
    drama_list = fields.JSONField()   # 番剧列表
    update_time = fields.DatetimeField()  # 数据更新时间

    class Meta:
        table = "Today_drama"
        table_description = "今日番剧表"


class Dramastatus(Model):
    id = fields.TextField(primary_key=True)   # 番剧id
    status = fields.TextField()  # 番剧状态
    image_header = fields.TextField(null=True)   # 番剧封面
    title = fields.TextField()   # 番剧名称
    begain_day = fields.DatetimeField()   # 番剧开始时间
    update_day = fields.DatetimeField(null=True)   # 番剧更新时间
    end_day = fields.DatetimeField(null=True)   # 番剧完结时间
    playsite = fields.JSONField()  # 番剧播放站点
    raw_json = fields.JSONField()   # 番剧原始数据
    update_time = fields.DatetimeField()  # 数据更新时间
    class Meta:
        table = "Drama_status"
        table_description = "番剧状态记录表"