"""Windows entry point. Remote pages receive no Python API or localhost endpoint."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

from presence import PresenceController, track_from_snapshot

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DATA = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'SoundCloudRPC'


def client_id() -> str | None:
    """A maintainer's bundled ID takes priority over first-run local setup."""
    for path in (ROOT / 'app_config.json', DATA / 'config.json'):
        try:
            value = str(json.loads(path.read_text(encoding='utf-8'))['client_id']).strip()
            if value.isascii() and value.isdigit() and 17 <= len(value) <= 22:
                return value
        except (OSError, ValueError, KeyError, TypeError):
            pass
    root = tk.Tk()
    root.withdraw()
    try:
        while True:
            value = simpledialog.askstring(
                'SoundCloud RPC — настройка',
                'Введите Application ID из Discord Developer Portal.\n'
                'Это публичный ID приложения, не токен.\n'
                'Автор сборки может указать его заранее в app_config.json.',
                parent=root,
            )
            if value is None:
                return None
            value = value.strip()
            if value.isascii() and value.isdigit() and 17 <= len(value) <= 22:
                (DATA / 'config.json').write_text(
                    json.dumps({'client_id': value}), encoding='utf-8')
                return value
            messagebox.showerror('Application ID', 'Нужен числовой Application ID.', parent=root)
    finally:
        root.destroy()


def run() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[RotatingFileHandler(DATA / 'app.log', maxBytes=500_000,
                                      backupCount=2, encoding='utf-8')],
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    app_id = client_id()
    if not app_id:
        return

    import webview
    from pypresence import Presence

    script = (ROOT / 'reader.js').read_text(encoding='utf-8')
    stop = threading.Event()
    ready = threading.Event()
    window = webview.create_window(
        'SoundCloud RPC · запуск', 'https://soundcloud.com/discover',
        width=1180, height=800, min_size=(800, 600),
    )
    window.events.loaded += lambda: ready.set()
    window.events.closed += lambda: stop.set()

    def worker():
        controller = PresenceController(lambda: Presence(
            app_id, connection_timeout=5, response_timeout=5))
        title = ''
        try:
            while not stop.is_set():
                track = None
                if ready.is_set():
                    try:
                        track = track_from_snapshot(window.evaluate_js(script))
                    except Exception:
                        logging.getLogger(__name__).debug('Page unavailable', exc_info=True)
                controller.tick(track)
                new_title = 'SoundCloud RPC · ' + controller.status
                if new_title != title and not stop.is_set():
                    try:
                        window.set_title(new_title)
                        title = new_title
                    except Exception:
                        pass
                stop.wait(2)
        finally:
            controller.close()

    thread = threading.Thread(target=worker, name='discord-rpc', daemon=True)
    try:
        # WebView2 profile stays in AppData, including SoundCloud login cookies.
        webview.settings['ALLOW_FILE_URLS'] = False
        webview.start(thread.start, gui='edgechromium', private_mode=False,
                      storage_path=str(DATA / 'browser'))
    finally:
        stop.set()
        if thread.ident:
            thread.join(timeout=7)


if __name__ == '__main__':
    try:
        run()
    except Exception:
        logging.exception('Application failed')
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            'SoundCloud RPC',
            'Не удалось запустить приложение.\n'
            'Проверьте Microsoft Edge WebView2 Runtime.\n'
            f'Подробности: {DATA / "app.log"}', parent=root,
        )
        root.destroy()
        raise
