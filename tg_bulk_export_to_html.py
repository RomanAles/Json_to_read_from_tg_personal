import argparse
import json
import os
import shutil
import html
from datetime import datetime
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(x, **_):
        return x

DEFAULT_BASE_DIR = Path(r"C:\Users\asas7\Downloads\Telegram Desktop")
CSS = """
body { font-family: sans-serif; background:#f4f6fb; color:#111; }
.container { max-width:900px; margin:20px auto; background:white; border-radius:8px;
             box-shadow:0 2px 8px rgba(0,0,0,0.06); padding:18px; }
.msg { padding:10px 12px; border-bottom:1px solid #eee; display:flex; gap:12px; align-items:flex-start; }
.avatar { width:40px; height:40px; border-radius:50%; background:#cbd5e1;
          display:inline-block; flex:0 0 40px; text-align:center; line-height:40px;
          color:#fff; font-weight:700; }
.body { flex:1; }
.meta { font-size:12px; color:#6b7280; margin-bottom:6px; }
.text { white-space:pre-wrap; font-size:15px; color:#0f172a; }
.media { margin-top:8px; }
.media img { max-width:420px; border-radius:6px; box-shadow:0 1px 4px rgba(0,0,0,0.08); }
.small { font-size:13px; color:#475569; }
.center { text-align:center; color:#64748b; margin:12px 0; }
"""


def ensure_dir(path: Path):
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
                else:
                    parts.append(html.escape(txt))
        return "".join(parts)
    return html.escape(str(text_field))


def iso_to_local(dt_str):
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt_str


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


def generate_html(messages, chat_name, out_dir: Path, media_src_base: Path):
    out_html_path = out_dir / "chat.html"
    media_dir = out_dir / "media"
    ensure_dir(out_dir)
    participants = {}
    for m in messages:
        author = m.get("from") or m.get("actor") or "Unknown"
        if author not in participants:
            participants[author] = author.strip()[:2].upper() or "U"

    html_parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        f"<title>{html.escape(chat_name)}</title>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<style>{CSS}</style></head><body><div class='container'>",
        f"<h2 class='center'>{html.escape(chat_name)}</h2>"
    ]

    def get_date(m):
        d = m.get("date")
        try:
            return datetime.fromisoformat(d)
        except Exception:
            return datetime.min

    for m in tqdm(sorted(messages, key=get_date), desc=f"Обработка {chat_name}"):
        author = m.get("from") or m.get("actor") or "Unknown"
        date = iso_to_local(m.get("date", ""))
        text_html = parse_text_field(m.get("text"))
        html_parts.append("<div class='msg'>")
        html_parts.append(f"<div class='avatar'>{html.escape(participants.get(author,'U'))}</div>")
        html_parts.append("<div class='body'>")
        html_parts.append(f"<div class='meta'><strong>{html.escape(author)}</strong> · {html.escape(date)}</div>")
        if text_html:
            html_parts.append(f"<div class='text'>{text_html}</div>")
        for key in ("photo", "file", "document"):
            if m.get(key):
                copied = copy_media_file(m[key], media_src_base, media_dir)
                if copied:
                    ext = copied.lower().split(".")[-1]
                    if ext in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
                        html_parts.append(f"<div class='media'><img src='media/{html.escape(copied)}'></div>")
                    else:
                        html_parts.append(f"<div class='media'><a href='media/{html.escape(copied)}'>{html.escape(copied)}</a></div>")
        html_parts.append("</div></div>")

    html_parts.append("</div></body></html>")
    out_html_path.write_text("\n".join(html_parts), encoding="utf-8")
    return out_html_path


def main():
    parser = argparse.ArgumentParser(description="Конвертирует все Telegram JSON экспорты в HTML")
    parser.add_argument("--base", default=str(DEFAULT_BASE_DIR),
                        help="Папка, где лежат экспорты Telegram (по умолчанию: Telegram Desktop)")
    parser.add_argument("--out", default="exports_html", help="Папка, куда сохранять результаты")
    args = parser.parse_args()

    base_dir = Path(args.base)
    out_root = Path(args.out)
    ensure_dir(out_root)

    export_dirs = [p for p in base_dir.iterdir() if p.is_dir() and any((p / n).exists() for n in ("messages.json", "result.json"))]

    if not export_dirs:
        print("Не найдено экспортов Telegram в", base_dir)
        return

    for chat_dir in export_dirs:
        json_file = chat_dir / "messages.json"
        if not json_file.exists():
            json_file = chat_dir / "result.json"
        if not json_file.exists():
            continue

        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Ошибка чтения {json_file}: {e}")
            continue

        messages = data.get("messages", [])
        chat_name = data.get("name") or chat_dir.name

        out_dir = out_root / chat_name
        out_html = generate_html(messages, chat_name, out_dir, chat_dir)
        print(f"Готово: {chat_name} → {out_html}")

    print("Все экспорты обработаны!")


if __name__ == "__main__":
    main()
