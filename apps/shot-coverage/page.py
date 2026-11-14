"""镜头条页面（镜头应用设计第 5 节，需求 5）：一排格子，一镜头一格；读过的亮，没读的灰，被需求引用的带标记。

数据全部来自核心层，不另算覆盖率：镜头列表和是否读过来自 `api.list_units`，被引用的镜头来自 `api.gather`，
起止时间来自缓存里登记时的那份清单，读取顺序、图片张数来自日志里的有效读取记录。
生成的是单文件 HTML：不联网、不嵌图片和视频画面（需求 5.5）。**没有脚本也显示最终状态**（亮灰在服务端就
写进 class）；内联的一小段脚本只用来回放：按读取顺序一格格点亮。
"""

import html
import json

import adapter


def valid_reads(store) -> list[dict]:
    """日志里的有效读取记录（单元校验值和清单当前的一致），按日志顺序。"""
    from refcov import coverage

    current = coverage.current_units(store.read_sources().get("sources", []))
    return [r for r in store.records() if r.get("type") == "read" and coverage.is_valid(r, current)]


def count_reads(store, source: str | None = None) -> list[dict]:
    """每个镜头参考源读过几个镜头、读了几次、送出几张图。只算有效读取。"""
    records = valid_reads(store)
    out = []
    for s in store.read_sources().get("sources", []):
        if s.get("adapter") != adapter.name or (source and s["id"] != source):
            continue
        mine = [r for r in records if r.get("source") == s["id"]]
        out.append({"source": s["id"], "shots": len(s.get("units", [])),
                    "read": len({r["unit"] for r in mine}), "reads": len(mine),
                    "images": sum(int(r.get("images") or 0) for r in mine)})
    return out


def collect(store, source: str | None = None) -> dict:
    """页面要的全部数据。`source` 不给时取第一个镜头参考源；没有时抛 `LookupError`。"""
    from refcov import api

    sources = [s for s in store.read_sources().get("sources", []) if s.get("adapter") == adapter.name]
    entry = next((s for s in sources if source in (None, s["id"])), None)
    if entry is None:
        raise LookupError("没有登记镜头适配器的参考源" + (f"（{source}）" if source else ""))
    sid = entry["id"]
    _, shots = adapter.parse_list((store.cache_dir / entry["sha256"]).read_bytes().decode("utf-8-sig"))
    read = {u["id"]: u["read"] for u in api.list_units(store, sid)}
    cited = {u for s, u in api.gather(store).cited if s == sid}
    first_reads, seen = [], set()
    for r in valid_reads(store):
        if r.get("source") == sid and r["unit"] not in seen:
            seen.add(r["unit"])
            first_reads.append({"unit": r["unit"], "time": r.get("time")})
    stats = next(row for row in count_reads(store, sid))
    cells = [{"id": adapter.shot_id(s), "start": s / 10, "end": e / 10, "ticks": e - s,
              "read": read.get(adapter.shot_id(s), False), "cited": adapter.shot_id(s) in cited}
             for s, e in shots]
    return {"source": sid, "cells": cells, "events": first_reads, **{k: stats[k] for k in ("shots", "read", "reads", "images")}}


CSS = """
:root{--bg:#14161a;--fg:#e8e6e1;--dim:#9aa0a6;--unread:#2b2f36;--read:#f2c94c;--cited:#56b6c2}
body{margin:0;padding:24px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}
.sum{margin:0 0 16px;color:var(--dim)} .sum b{color:var(--fg)}
.strip{display:flex;gap:2px;align-items:stretch;height:56px}
.cell{flex:1 1 0;min-width:3px;background:var(--unread);border-top:5px solid transparent;border-radius:2px}
.cell.read{background:var(--read)}
.cell.cited{border-top-color:var(--cited)}
.legend{margin:12px 0;color:var(--dim);font-size:13px}
.legend i{display:inline-block;width:12px;height:12px;margin:0 4px 0 12px;vertical-align:-1px;border-radius:2px}
.controls{display:none;margin:12px 0;gap:8px;align-items:center}
.controls input{flex:1}
button{background:#2b2f36;color:var(--fg);border:0;border-radius:4px;padding:4px 12px;cursor:pointer}
.limits{margin-top:20px;color:var(--dim);font-size:13px;max-width:60em}
"""

LIMITS = ("Shots are hard cuts only. A shot with a slow zoom or a fade is one unit, and one keyframe from its "
          "middle does not show text or motion that appears elsewhere in the shot. Reading a shot's keyframe is "
          "not the same as having seen every frame of it.")

SCRIPT = """
(function(){
  var ev = JSON.parse(document.getElementById('events').textContent);
  var cells = {}; document.querySelectorAll('.cell').forEach(function(c){ cells[c.dataset.id] = c; });
  var box = document.querySelector('.controls'), range = document.getElementById('pos'),
      label = document.getElementById('poslabel'), play = document.getElementById('play'), timer = null;
  if (!ev.length) return;
  box.style.display = 'flex'; range.max = ev.length; range.value = ev.length;
  function show(n){
    Object.keys(cells).forEach(function(k){ cells[k].classList.remove('read'); });
    for (var i = 0; i < n; i++) cells[ev[i].unit].classList.add('read');
    range.value = n; label.textContent = n + ' / ' + ev.length + (n ? '  ' + (ev[n-1].time || '') : '');
  }
  function stop(){ if (timer) { clearInterval(timer); timer = null; } play.textContent = 'Play'; }
  play.onclick = function(){
    if (timer) { stop(); return; }
    var n = (+range.value >= ev.length) ? 0 : +range.value; show(n); play.textContent = 'Pause';
    timer = setInterval(function(){ if (n >= ev.length) { stop(); return; } n++; show(n); }, 300);
  };
  range.oninput = function(){ stop(); show(+range.value); };
  show(ev.length);
})();
"""


def _cell(c: dict) -> str:
    """一格：亮灰和被引用的标记都写进 class（没有脚本也显示最终状态）；宽度按时长成比例。"""
    classes = "cell" + (" read" if c["read"] else "") + (" cited" if c["cited"] else "")
    status = ("read" if c["read"] else "not read") + (", cited by a requirement" if c["cited"] else "")
    cid = html.escape(c["id"])
    title = f"{cid}  {c['start']:.1f}-{c['end']:.1f} s  {status}"
    return f'<div class="{classes}" style="flex-grow:{c["ticks"]}" data-id="{cid}" title="{title}"></div>'


def render_strip(data: dict) -> str:
    """把 `collect` 的结果写成单文件 HTML。纯函数，不读文件。"""
    esc = html.escape
    cells = "\n".join(_cell(c) for c in data["cells"])
    events = json.dumps(data["events"], ensure_ascii=True).replace("<", "\\u003c")  # 数据里的 < 不能提前结束 script 标签
    source = esc(data["source"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Shot coverage: {source}</title>
<style>{CSS}</style></head><body>
<h1>Shot coverage</h1>
<p class="sum">Source <code>{source}</code>: read <b>{data['read']}</b> of <b>{data['shots']}</b> shots,
{data['reads']} reads, <b>{data['images']}</b> keyframe images sent.</p>
<div class="strip" id="strip">
{cells}
</div>
<div class="legend"><i style="background:var(--read)"></i>read<i style="background:var(--unread)"></i>not read<i style="background:var(--cited)"></i>cited by a requirement (top edge)</div>
<div class="controls"><button id="play" type="button">Play</button><input id="pos" type="range" min="0" max="0" value="0"><span id="poslabel"></span></div>
<p class="limits">{esc(LIMITS)}</p>
<script id="events" type="application/json">{events}</script>
<script>{SCRIPT}</script>
</body></html>
"""
