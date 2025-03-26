<!-- markdownlint-disable MD033 MD036 MD041 -->

<p align="center">
  <a href="https://huanxinbot.com/"><img src="https://raw.githubusercontent.com/huanxin996/nonebot_plugin_hx-yinying/main/.venv/hx_img.png" width="200" height="200" alt="这里放一张oc饭🤤"></a>
</p>

<div align="center">

# 日漫更新推送

_✨ 实时追踪最新动漫，自动推送更新信息 ✨_

</div>

## 📝 插件说明

这是一个基于 NoneBot2 的动漫更新推送插件，可以：

- 查看今日更新的番剧
- 获取本周番剧时间表
- 查询特定番剧的详细信息
- 设置自动推送更新提醒

## 💿 安装

### 使用 pip 安装（推荐）

```bash
pip install nonebot-plugin-animepush
```

## ⚙️ 配置说明

在 `.env` 文件中添加以下配置项：

| 配置项 | 类型 | 默认值 | 说明 | 必填 |
|:-----:|:----:|:----:|:----:|:----:|
| animepush_image_quality | int | 30 | 图片渲染质量(越高图片越大) | 否 |
| animepush_image_wait | int | 5 | 图片渲染超时时间(秒) | 否 |
| animepush_fonts_medium | str | None | 中等字重字体路径 | 否 |
| animepush_fonts_bold | str | None | 粗体字重字体路径 | 否 |

## 🎯 使用指南

### 基础命令

- `/今日番剧` - 查看今天更新的动漫
- `/本周番剧` - 查看本周动漫时间表
- `/番剧详情 [番剧id]` - 查看指定番剧的详细信息
- `/更新番剧数据` - 刷新一次番剧数据

### 使用示例

```
/今日番剧
> 返回今日更新的番剧列表图片

/番剧详情 114514
> 返回该番剧的详细信息
```

## ⚠️ 注意事项

1. 首次使用时请确保配置正确
2. 图片渲染可能需要一定时间，请耐心等待
3. 推荐使用自定义字体以获得最佳显示效果
4. 自定义字体请将字体文件放置于 插件目录的`fonts` 目录下，并修改 `.env` 文件中的配置项

## 🤝 贡献

欢迎提交 Issue 和 Pull Request

## 📄 许可证

MIT License
