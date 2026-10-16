# -*- coding: utf-8 -*-
"""第二人格英语练习系统 —— 本地 Flask 应用

页面：/ 日历首页 | /input/<date> 输入页(Part A) | /output/<date> 输出页(Part B/C)
      /history 回看列表 | /history/<videoId> 某视频历史
接口：POST /save 把练习写成 JSON 落盘到 static/saves/（含 ts 与 audio 字段）
      POST /save-audio 接收浏览器录制的音频，按 date_type_ts 与文字记录同名关联
"""
import json
import os
import re
import calendar as _cal
from datetime import datetime

from flask import Flask, render_template, request, jsonify, abort

BASE = os.path.dirname(os.path.abspath(__file__))
CONTENT_PATH = os.path.join(BASE, "content.json")
SAVES = os.path.join(BASE, "static", "saves")
os.makedirs(SAVES, exist_ok=True)

with open(CONTENT_PATH, encoding="utf-8") as f:
    CONTENT = json.load(f)

app = Flask(__name__)


AUDIO_EXTS = (".webm", ".ogg", ".mp4", ".m4a")


def _audio_for(base):
    """给定 json 文件名去扩展名后的 base，查找同名音频文件，返回可访问 URL 或 None。"""
    for ext in AUDIO_EXTS:
        cand = base + ext
        if os.path.exists(os.path.join(SAVES, cand)):
            return "/static/saves/" + cand
    return None


def load_records():
    recs = []
    for fn in os.listdir(SAVES):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(SAVES, fn), encoding="utf-8") as f:
                d = json.load(f)
            d["_file"] = fn
            d["audio"] = _audio_for(fn[:-5])  # 去掉 .json
            recs.append(d)
        except Exception:
            continue
    recs.sort(key=lambda r: r.get("savedAt", ""), reverse=True)
    return recs


def schedule_entry(date):
    return next((s for s in CONTENT["schedule"] if s["date"] == date), None)


@app.route("/")
def index():
    schedule = CONTENT["schedule"]
    start = datetime.strptime(CONTENT["startDate"], "%Y-%m-%d")
    # 年/月由查询参数决定，缺省落到计划起始月
    try:
        year = int(request.args.get("year", start.year))
        month = int(request.args.get("month", start.month))
    except (ValueError, TypeError):
        year, month = start.year, start.month
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1

    first_weekday, ndays = _cal.monthrange(year, month)  # Monday = 0
    cells = [None] * first_weekday
    for d in range(1, ndays + 1):
        ds = f"{year:04d}-{month:02d}-{d:02d}"
        cells.append({"day": d, "date": ds, "entry": schedule_entry(ds)})

    prefix = f"{year:04d}-{month:02d}"
    plan = sorted([s for s in schedule if s["date"].startswith(prefix)], key=lambda s: s["date"])

    today = datetime.now().strftime("%Y-%m-%d")

    prev_month, prev_year = month - 1, year
    if prev_month < 1:
        prev_month, prev_year = 12, year - 1
    next_month, next_year = month + 1, year
    if next_month > 12:
        next_month, next_year = 1, year + 1

    years = list(range(start.year - 1, start.year + 3))

    # 完成态：扫描 saves，按日期聚合 input/output 是否已保存
    done = {}
    for r in load_records():
        d = r.get("date")
        t = r.get("type")
        if d and t in ("input", "output"):
            slot = done.setdefault(d, {"input": False, "output": False})
            slot[t] = True

    return render_template(
        "index.html",
        cells=cells,
        today=today,
        year=year,
        month=month,
        month_name=f"{year}年{month}月",
        plan=plan,
        videos=CONTENT["videos"],
        prev=(prev_year, prev_month),
        next=(next_year, next_month),
        years=years,
        done=done,
    )


@app.route("/input/<date>")
def input_page(date):
    s = schedule_entry(date)
    if not s:
        abort(404)
    return render_template("input.html", date=date, entry=s, video=CONTENT["videos"][s["videoId"]])


@app.route("/output/<date>")
def output_page(date):
    s = schedule_entry(date)
    if not s:
        abort(404)
    return render_template("output.html", date=date, entry=s, video=CONTENT["videos"][s["videoId"]])


@app.route("/history")
@app.route("/history/<videoId>")
def history(videoId=None):
    recs = load_records()
    if videoId:
        recs = [r for r in recs if r.get("videoId") == videoId]
    for r in recs:
        v = CONTENT["videos"].get(r.get("videoId"), {})
        r["_title"] = v.get("title", "?")
        r["_creator"] = v.get("creator", "?")
    return render_template("history.html", records=recs)


TS_RE = re.compile(r"^\d{8}T\d{6}$")


@app.route("/save", methods=["POST"])
def save():
    data = request.get_json(force=True, silent=True) or {}
    date = data.get("date", "")
    typ = data.get("type", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date) or typ not in ("input", "output"):
        return jsonify({"ok": False, "error": "bad params"}), 400
    now = datetime.now()
    # 优先用前端传入的 ts（与录音同名关联），否则后端生成
    ts = data.get("ts") if TS_RE.match(str(data.get("ts", ""))) else None
    if not ts:
        ts = now.strftime("%Y%m%dT%H%M%S")
    data["savedAt"] = now.strftime("%Y-%m-%dT%H:%M:%S")
    if "audio" not in data:
        data["audio"] = None
    fn = f"{date}_{typ}_{ts}.json"
    with open(os.path.join(SAVES, fn), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "file": fn, "ts": ts})


@app.route("/save-audio", methods=["POST"])
def save_audio():
    """接收浏览器 MediaRecorder 录制的音频，按 date_type_ts 命名，与文字记录同名关联。"""
    date = request.form.get("date", "")
    typ = request.form.get("type", "")
    ts = request.form.get("ts", "")
    f = request.files.get("audio")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date) or typ not in ("input", "output") or not TS_RE.match(ts) or not f:
        return jsonify({"ok": False, "error": "bad params"}), 400
    orig = (f.filename or "").lower()
    ext = ".webm"
    for e in AUDIO_EXTS:
        if orig.endswith(e):
            ext = e
            break
    fn = f"{date}_{typ}_{ts}{ext}"
    f.save(os.path.join(SAVES, fn))
    return jsonify({"ok": True, "file": fn})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
