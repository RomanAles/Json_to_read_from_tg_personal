import argparse
import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

try:
    from tqdm import tqdm
except Exception:
    def tqdm(x, **_):
        return x
CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial; background:#f5f7fb; color:#111; }
.container { max-width:900px; margin:20px auto; background:white; border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,0.06); padding:18px; }
.msg { padding:10px 12px; border-bottom:1px solid #eef1f6; display:flex; gap:12px; align-items:flex-start; }
.avatar { width:40px; height:40px; border-radius:50%; background:#cbd5e1; display:inline-block; flex:0 0 40px; text-align:center; line-height:40px; color:#fff; font-weight:700; }
.body { flex:1; }
.meta { font-size:12px; color:#6b7280; margin-bottom:6px; }
.text { white-space:pre-wrap; font-size:15px; color:#0f172a; }
.media { margin-top:8px; }
.media img { max-width:420px; border-radius:6px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }
.small { font-size:13px; color:#475569; }
.center { text-align:center; color:#64748b; margin:12px 0; }
"""

def ensure_dir(path: Path):
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

def parse_text_field(text_field):
    if text_field is None:
        return ""
    if isinstance(text_field, str):
        return html.escape(text_field)
    if isinstance(text_field, list):
        parts = []
        for part in text_field:
            if isinstance(part, str):
                parts.append(html.escape(part))
            elif isinstance(part, dict):
                t = part.get("type")
                txt = part.get("text", "")
                if t == "link" and part.get("href"):
                    href = html.escape(part["href"])
                    parts.append(f'<a href="{href}" target="_blank">{html.escape(txt)}</a>')
                elif t == "bot_command":
                    parts.append(html.escape(txt))
                else:
                    parts.append(html.escape(txt))
            else:
                parts.append(html.escape(str(part)))
        return "".join(parts)
    return html.escape(str(text_field))

def iso_to_local(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
    except Exception:
        try:
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return dt_str
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def copy_media_file(media_path, src_base: Path, dst_media_dir: Path):
    if not media_path:
        return None
    src = Path(media_path)
    if not src.is_absolute():
        src = src_base / src
    if not src.exists():
        for try_dir in ("media", "files", ""):
            candidate = src_base / try_dir / Path(media_path).name
            if candidate.exists():
                src = candidate
                break
    if not src.exists():
        return None
    ensure_dir(dst_media_dir)
    dst = dst_media_dir / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
    return dst.name

def generate_html(messages, out_html_path: Path, media_src_base: Path, embed_media_dir_name="media"):
    out_dir = out_html_path.parent
    media_dst_dir = out_dir / embed_media_dir_name
    ensure_dir(out_dir)
    participants = {}
    for m in messages:
        author = m.get("from") or m.get("actor") or "Unknown"
        if author not in participants:
            participants[author] = author.strip()[:2].upper() if author.strip() else "U"
    html_parts = []
    html_parts.append("<!doctype html>\n<html lang='ru'>\n<head>\n<meta charset='utf-8'>")
    html_parts.append(f"<title>Telegram export — {html.escape(out_html_path.stem)}</title>")
    html_parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    html_parts.append(f"<style>{CSS}</style>\n</head>\n<body>\n<div class='container'>")
    html_parts.append(f"<h2 class='center'>Чат — экспорт Telegram</h2>")
    def get_date(m):
        d = m.get("date")
        if d is None:
            return datetime.min
        try:
            return datetime.fromisoformat(d)
        except Exception:
            try:
                return datetime.strptime(d, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                return datetime.min
    messages_sorted = sorted(messages, key=get_date)
    for m in tqdm(messages_sorted, desc="Processing messages"):
        author = m.get("from") or m.get("actor") or "Unknown"
        date = iso_to_local(m.get("date", ""))
        text_html = parse_text_field(m.get("text"))
        html_parts.append("<div class='msg'>")
        initial = participants.get(author, "U")
        html_parts.append(f"<div class='avatar' title='{html.escape(author)}'>{html.escape(initial)}</div>")
        html_parts.append("<div class='body'>")
        html_parts.append(f"<div class='meta'><strong>{html.escape(author)}</strong> · <span class='small'>{html.escape(date)}</span></div>")
        if text_html:
            html_parts.append(f"<div class='text'>{text_html}</div>")
        media_html_parts = []
        if m.get("photo"):
            copied = copy_media_file(m["photo"], media_src_base, media_dst_dir)
            if copied:
                media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'><img src='{embed_media_dir_name}/{html.escape(copied)}' alt='photo'></a></div>")
        if m.get("file"):
            copied = copy_media_file(m["file"], media_src_base, media_dst_dir)
            if copied:
                ext = copied.lower().split('.')[-1]
                if ext in ("jpg","jpeg","png","gif","webp","bmp","svg","heic"):
                    media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'><img src='{embed_media_dir_name}/{html.escape(copied)}' alt='file'></a></div>")
                else:
                    media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'>Скачать файл: {html.escape(copied)}</a></div>")
        if m.get("document"):
            doc = m["document"]
            if isinstance(doc, dict) and doc.get("file"):
                copied = copy_media_file(doc.get("file"), media_src_base, media_dst_dir)
            else:
                copied = copy_media_file(doc, media_src_base, media_dst_dir)
            if copied:
                ext = copied.lower().split('.')[-1]
                if ext in ("jpg","jpeg","png","gif","webp","bmp","svg","heic"):
                    media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'><img src='{embed_media_dir_name}/{html.escape(copied)}'></a></div>")
                else:
                    media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'>Скачать документ: {html.escape(copied)}</a></div>")
        if m.get("media"):
            media = m["media"]
            if isinstance(media, dict):
                possible = media.get("file") or media.get("photo") or media.get("path") or media.get("document")
                if possible:
                    copied = copy_media_file(possible, media_src_base, media_dst_dir)
                    if copied:
                        if copied.lower().split('.')[-1] in ("jpg","jpeg","png","gif","webp","bmp","svg","heic"):
                            media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'><img src='{embed_media_dir_name}/{html.escape(copied)}'></a></div>")
                        else:
                            media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'>Скачать: {html.escape(copied)}</a></div>")
            elif isinstance(media, str):
                copied = copy_media_file(media, media_src_base, media_dst_dir)
                if copied:
                    if copied.lower().split('.')[-1] in ("jpg","jpeg","png","gif","webp","bmp","svg","heic"):
                        media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'><img src='{embed_media_dir_name}/{html.escape(copied)}'></a></div>")
                    else:
                        media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'>Скачать: {html.escape(copied)}</a></div>")
        if m.get("attachments"):
            for att in m["attachments"]:
                if isinstance(att, dict) and att.get("file"):
                    copied = copy_media_file(att["file"], media_src_base, media_dst_dir)
                    if copied:
                        media_html_parts.append(f"<div class='media'><a href='{embed_media_dir_name}/{html.escape(copied)}' target='_blank'>{html.escape(copied)}</a></div>")
        if media_html_parts:
            html_parts.extend(media_html_parts)
        if m.get("forwarded_from"):
            html_parts.append(f"<div class='small'>Переслано от: {html.escape(str(m.get('forwarded_from')))}</div>")
        if m.get("reply_to"):
            html_parts.append(f"<div class='small'>В ответ на сообщение id: {html.escape(str(m.get('reply_to')))}</div>")
        html_parts.append("</div>")
        html_parts.append("</div>")
    html_parts.append("</div>\n</body>\n</html>")
    html_text = "\n".join(html_parts)
    with out_html_path.open("w", encoding="utf-8") as f:
        f.write(html_text)
    return out_html_path, media_dst_dir

def main():
    parser = argparse.ArgumentParser(description="Convert Telegram messages.json export to HTML")
    parser.add_argument("json", help="Путь к messages.json (экспорт Telegram)")
    parser.add_argument("--out", "-o", help="Путь к итоговому HTML (по умолчанию: ./chat.html)", default="chat.html")
    parser.add_argument("--media-src", "-m", help="Корневая папка, где лежат файлы экспорта (по умолчанию — папка с messages.json)", default=None)
    parser.add_argument("--media-dir-name", help="Имя папки рядом с html, куда копировать медиа (по умолчанию 'media')", default="media")
    args = parser.parse_args()
    json_path = Path(args.json)
    if not json_path.exists():
        print("Файл JSON не найден:", json_path)
        return
    media_src_base = Path(args.media_src) if args.media_src else json_path.parent
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("messages"):
        messages = data["messages"]
    elif isinstance(data, list):
        messages = data
    else:
        messages = data.get("messages") or []
    out_html_path = Path(args.out)
    generate_html(messages, out_html_path, media_src_base, embed_media_dir_name=args.media_dir_name)
    print("Готово. HTML:", out_html_path.resolve())
    print("Медиа (если были) скопированы в папку:", (out_html_path.parent / args.media_dir_name).resolve())

if __name__ == "__main__":
    main()
