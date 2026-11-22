"""Build the optional, self-hosted Chinese display subset (fonttools + brotli)."""
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlretrieve

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

FRONTEND = Path(__file__).resolve().parents[1]
UPSTREAM = "https://raw.githubusercontent.com/google/fonts/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5/ofl/notoserifsc/"
# Only display lettering is bundled. Dynamic names use the local Songti stack.
LETTERING = """拓展边界，让灵感运行。每一个插件都是种新的可能从用途开始值得一试
精选作品持续生长最近更新由热爱驱动社区创作者下可能你造猜你喜欢还喜欢
找到你的下一块拼图探索发现市场档案技能资料版本说明使用指南消息中心服务状态
控制台工作管理设置收藏关注推荐阅读获取安装评论讨论返回索引分类常用主题
这份未聊天互动休闲娱乐信息资讯实用工具效率自动化记忆知识图像媒体安全
头版目录专栏开源印刷工坊藏墨地图查看全部热门翻阅文献个人展示消息通知
最近更新社区作者创作工作台档案社区信箱未找到这一页三项服务检查均已通过正在部分
缺页编辑部公报审计日志名录新建公告身份确认失败登录后访问后台需要员权限评论核治理
市场运行总览策展专访人物刊登作品书目技能总目个人简历查阅此篇来源栏目"""

with TemporaryDirectory() as tmp:
    src = Path(tmp) / "source.ttf"
    urlretrieve(UPSTREAM + "NotoSerifSC%5Bwght%5D.ttf", src)
    font = TTFont(src)
    sub = subset.Subsetter()
    sub.populate(text=LETTERING)
    sub.subset(font)
    font = instantiateVariableFont(font, {"wght": 800}, inplace=True)
    font.flavor = "woff2"
    output = FRONTEND / "src/assets/fonts/mofox-editorial-sc-800.woff2"
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(output)
    licenses = FRONTEND / "public/font-licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    urlretrieve(UPSTREAM + "OFL.txt", licenses / "Noto-Serif-SC.txt")
    print(output.name, output.stat().st_size)
