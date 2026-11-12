"""Validated track model and reconnecting Discord state machine (GUI independent)."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
import math
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
    position: float | None = field(default=None, compare=False)
    duration: float | None = None
    sampled_at: float = field(default_factory=time.time, compare=False)

    @property
    def started_at(self) -> float | None:
        if self.position is None or self.duration is None:
            return None
        return self.sampled_at - self.position

    def fields(self) -> dict:
        # Listening cards use details for the prominent song line and state for
        # the artist. Two zero-width spaces suppress the visible status suffix;
        # omitting name would restore the registered application's name.
        result = {'name': '\u200b\u200b',
                  'details': self.title.ljust(2),
                  'state': (self.artist or 'SoundCloud').ljust(2)}
        if self.artwork:
            # Listening cards can show the artwork caption as an album line.
            # The song already has its own details line; do not repeat it there.
            result['large_image'] = self.artwork
        if self.url:
            result['buttons'] = [{'label': 'Open on SoundCloud', 'url': self.url}]
        if self.started_at is not None:
            result['start'] = int(self.started_at)
            result['end'] = int(self.started_at + self.duration)
        return result


def track_from_snapshot(data: object) -> Track | None:
    if not isinstance(data, dict) or data.get('playing') is not True:
        return None
    title = text(data.get('title'))
    if not title:
        return None
    def seconds(key):
        value = data.get(key)
        if (isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and 0 <= value <= 7 * 24 * 3600):
            return float(value)
        return None
    position, duration = seconds('position'), seconds('duration')
    if duration is None or duration <= 0 or position is None or position > duration:
        position = duration = None
    return Track(title, text(data.get('artist')),
                 public_url(data.get('artwork'), 'art'),
                 public_url(data.get('url'), 'track'), position, duration)


class PresenceController:
    def __init__(self, factory, clock=time.monotonic, activity_type=None):
        self.factory = factory
        self.clock = clock
        self.activity_type = activity_type
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
            timeline_changed = False
            if track and self.previous:
                before, after = self.previous.started_at, track.started_at
                timeline_changed = ((before is None) != (after is None)
                    or (before is not None and after is not None and abs(before - after) > 2.5))
            if (((track != self.previous or timeline_changed) and now >= self.publish_at)
                    or now >= self.heartbeat_at):
                if track is None:
                    self.rpc.clear()
                else:
                    fields = track.fields()
                    if self.activity_type is not None:
                        fields['activity_type'] = self.activity_type
                    self.rpc.update(**fields)
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
