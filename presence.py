"""Validated track model and reconnecting Discord state machine (GUI independent)."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from urllib.parse import urlparse

log = logging.getLogger(__name__)


def text(value: object) -> str:
    # Discord has field size limits; keep multi-byte titles comfortably below them.
    if not isinstance(value, str):
        return ''
    return value.strip().encode('utf-8')[:120].decode('utf-8', errors='ignore')


def public_url(value: object, kind: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        return ''
    try:
        url = urlparse(value)
        host = url.hostname or ''
        allowed = (host in ('soundcloud.com', 'www.soundcloud.com') if kind == 'track'
                   else host.endswith('.sndcdn.com'))
        if url.scheme == 'https' and allowed and not url.username and not url.password:
            return value
    except ValueError:
        pass
    return ''


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    artwork: str = ''
    url: str = ''

    def fields(self) -> dict:
        result = {'details': self.title.ljust(2),
                  'state': (self.artist or 'SoundCloud').ljust(2)}
        if self.artwork:
            result.update(large_image=self.artwork, large_text=self.title.ljust(2))
        if self.url:
            result['buttons'] = [{'label': 'Open on SoundCloud', 'url': self.url}]
        return result


def track_from_snapshot(data: object) -> Track | None:
    if not isinstance(data, dict) or data.get('playing') is not True:
        return None
    title = text(data.get('title'))
    if not title:
        return None
    return Track(title, text(data.get('artist')),
                 public_url(data.get('artwork'), 'art'),
                 public_url(data.get('url'), 'track'))


class PresenceController:
    def __init__(self, factory, clock=time.monotonic):
        self.factory = factory
        self.clock = clock
        self.rpc = None
        self.previous = None
        self.retry_at = 0.0
        self.publish_at = 0.0
        self.heartbeat_at = 0.0
        self.status = 'ожидание Discord'

    def tick(self, track: Track | None) -> None:
        now = self.clock()
        if self.rpc is None and now < self.retry_at:
            return
        try:
            if self.rpc is None:
                self.rpc = self.factory()
                self.rpc.connect()
                self.previous = None
                self.publish_at = 0
                # Remove any old activity for this process before publishing.
                self.rpc.clear()
            if ((track != self.previous and now >= self.publish_at)
                    or now >= self.heartbeat_at):
                if track is None:
                    self.rpc.clear()
                else:
                    self.rpc.update(**track.fields())
                self.previous = track
                self.publish_at = now + 5
                self.heartbeat_at = now + 30
            self.status = ('Discord подключён' if track else 'пауза / выберите трек')
        except Exception as exc:
            log.warning('Discord RPC unavailable: %s', exc)
            self._disconnect()
            self.retry_at = now + 10
            self.status = 'откройте Discord / проверьте Application ID'

    def _disconnect(self):
        if self.rpc is not None:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None
        self.previous = None

    def close(self):
        if self.rpc is not None:
            try:
                self.rpc.clear()
            except Exception:
                pass
        self._disconnect()
