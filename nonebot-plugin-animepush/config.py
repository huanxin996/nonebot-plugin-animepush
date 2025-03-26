__author__ = "HuanXin"

import nonebot
from pydantic import BaseModel, Field
from nonebot import get_plugin_config


class Config(BaseModel):
    version: str = "0.0.1"
    animepush_image_quality: int = Field(default=30, ge=1, le=100, description="图片渲染质量(1-100)")
    animepush_image_wait : int = Field(default=5, ge=1, le=10, description="图片渲染等待时间(秒)")
    animepush_fonts_medium : str = Field(default=None, description="中等字重字体文件路径")
    animepush_fonts_bold : str = Field(default=None, description="粗体字重字体文件路径")

global_config = nonebot.get_driver().config
config = get_plugin_config(Config)