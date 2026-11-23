"""Build evidence-first daily reports from timestamped speech, locally."""
from collections import defaultdict
from datetime import datetime
import re

CUE = re.compile(r"^- \[(\d{2}:[\d:.]+) – [\d:.]+\] (.+)$", re.MULTILINE)
TOPICS = {
    "A股与风险": "A股|大盘|沪深|下跌|反弹|风险",
    "蓝筹与防御": "蓝筹|防御|现金奶牛|银行|电力|央企|国企",
    "估值": "估值|市盈率|市净率|高估|低估",
    "外部市场": "美股|纳指|泡沫|外部风险|海外",
    "配置与交易": "仓位|持币|配置|买入|卖出|追涨杀跌",
    "商品": "黄金|白银|原油",
}
NUMBERS = re.compile(r"\d|百分之|千[零一二三四五六七八九]|[万亿]元")


def reports(root, videos):
    groups = defaultdict(list)
    for video in videos.values():
        if video.get("transcript") and video.get("published"):
            groups[video["transcript"].split("/")[0]].append(video)
    previous = None
    for date, entries in sorted(groups.items()):
        lines = [f"# 李大霄视频每日研究 {date}", "",
                 "以下引文为机器识别原文，按主题摘录。完整语境以对应时间戳和原视频为准。", ""]
        topics_today = set()
        for video in sorted(entries, key=lambda v: v["published"]):
            source = root / video["transcript"]
            if not source.is_file():
                continue
            cues = CUE.findall(source.read_text(encoding="utf-8"))
            published = datetime.fromtimestamp(video["published"]).astimezone().isoformat(timespec="minutes")
            lines.extend([f"## {video['title']}", "", f"{published} · [原视频]({video['url']})", "",
                          "### 原始讲话中的主题线索", ""])
            for topic, pattern in TOPICS.items():
                matches = [(when, text) for when, text in cues if re.search(pattern, text, re.I)]
                if matches:
                    topics_today.add(topic)
                    lines.append(f"- **{topic}**")
                    lines.extend(f"  - {when} {text}" for when, text in matches[:3])
            numbers = [(when, text) for when, text in cues if NUMBERS.search(text)]
            lines.extend(["", "### 重要数据待独立核实", ""])
            lines.extend(f"- {when} {text}" for when, text in numbers[:10])
            if not numbers:
                lines.append("本次未自动提取到数字线索。")
            lines.append("")
        lines.extend(["## 解读与外部验证", "",
                      "主题命中只表示讲话出现相关表述。市场方向、仓位和立场变化需结合原话判断。",
                      "外部财务与行情核验尚未执行。实际交易继续依据 A 股 V8.3 独立估值与风险管理。", "",
                      "## 与上一有稿日期对比", ""])
        if previous is None:
            lines.append("暂无更早的语音归档可比。")
        else:
            added = sorted(topics_today - previous)
            removed = sorted(previous - topics_today)
            lines.append("新增提及主题：" + ("、".join(added) if added else "无"))
            lines.append("未再次检出主题：" + ("、".join(removed) if removed else "无"))
        previous = topics_today
        yield f"research/{date}.md", "\n".join(lines) + "\n"
