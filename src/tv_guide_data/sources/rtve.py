from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from ..config import SourceConfig
from ..models import Channel, Programme

USER_AGENT = "tv-guide-data/0.1 (+https://github.com/)"


def _normalise(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _fetch(url: str, timeout: int = 45) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"},
        timeout=timeout,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def _json_blobs(page: str) -> Iterable[Any]:
    soup = BeautifulSoup(page, "html.parser")
    for script in soup.find_all("script"):
        text = script.string or script.get_text("", strip=True)
        if not text:
            continue
        script_type = (script.get("type") or "").lower()
        candidates: list[str] = []
        if "json" in script_type or text[:1] in "[{":
            candidates.append(text)
        for pattern in (
            r"__NEXT_DATA__\s*=\s*({.*?})\s*;?\s*$",
            r"window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;?",
        ):
            match = re.search(pattern, text, re.S)
            if match:
                candidates.append(match.group(1))
        for candidate in candidates:
            try:
                yield json.loads(candidate)
            except json.JSONDecodeError:
                continue


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _first(obj: dict[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).casefold(): value for key, value in obj.items()}
    for name in names:
        value = lowered.get(name.casefold())
        if value not in (None, "", []):
            return value
    return None


def _parse_datetime(value: Any, timezone_name: str, date_hint: Any = None) -> datetime | None:
    tz = ZoneInfo(timezone_name)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        stamp = float(value) / (1000 if value > 10_000_000_000 else 1)
        try:
            return datetime.fromtimestamp(stamp, tz=UTC).astimezone(tz)
        except (ValueError, OSError):
            return None

    text = str(value).strip()
    if re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", text):
        if not date_hint:
            return None
        try:
            day = datetime.fromisoformat(str(date_hint)[:10]).date()
            parsed_time = datetime.strptime(
                text, "%H:%M:%S" if text.count(":") == 2 else "%H:%M"
            ).time()
            return datetime.combine(day, parsed_time, tz)
        except ValueError:
            return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed.astimezone(tz)
    except ValueError:
        pass

    for pattern in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def _match_channel(obj: dict[str, Any], channels: tuple[Channel, ...]) -> Channel | None:
    possible_values: list[str] = []
    for key in (
        "channel",
        "canal",
        "channelName",
        "channel_name",
        "cadena",
        "service",
        "station",
        "slug",
    ):
        value = _first(obj, (key,))
        if isinstance(value, dict):
            possible_values.extend(
                str(item) for item in value.values() if isinstance(item, (str, int))
            )
        elif value is not None:
            possible_values.append(str(value))

    joined = " | ".join(_normalise(item) for item in possible_values)
    for channel in channels:
        candidates = (*channel.aliases, channel.source_id)
        if any(_normalise(candidate) in joined for candidate in candidates if candidate):
            return channel
    return None


def _programme_from_object(obj: dict[str, Any], config: SourceConfig) -> Programme | None:
    channel = _match_channel(obj, config.channels)
    if not channel:
        return None

    title = _first(obj, ("title", "titulo", "name", "nombre", "programTitle", "program_name"))
    if isinstance(title, dict):
        title = _first(title, ("text", "value", "name", "title"))
    if not title or len(str(title).strip()) < 2:
        return None

    date_hint = _first(obj, ("date", "fecha", "broadcastDate", "day"))
    start = _parse_datetime(
        _first(
            obj,
            ("start", "startDate", "startTime", "inicio", "horaInicio", "begin", "emissionStart"),
        ),
        config.timezone,
        date_hint,
    )
    stop = _parse_datetime(
        _first(obj, ("end", "endDate", "endTime", "fin", "horaFin", "stop", "emissionEnd")),
        config.timezone,
        date_hint,
    )
    duration = _first(obj, ("duration", "duracion", "length"))
    if start and not stop and duration is not None:
        try:
            seconds = float(duration)
            if seconds < 600:
                seconds *= 60
            stop = start + timedelta(seconds=seconds)
        except (TypeError, ValueError):
            pass
    if not start or not stop or stop <= start:
        return None

    description = (
        _first(obj, ("description", "descripcion", "summary", "sinopsis", "shortDescription")) or ""
    )
    category = _first(obj, ("category", "categoria", "genre", "genero")) or ""
    link = _first(obj, ("url", "htmlUrl", "link", "web")) or ""
    icon = _first(obj, ("image", "icon", "thumbnail", "photo", "imagen")) or ""
    if isinstance(icon, dict):
        icon = _first(icon, ("url", "src", "image")) or ""

    return Programme(
        channel_id=channel.xmltv_id,
        start=start,
        stop=stop,
        title=str(title).strip(),
        description=str(description).strip(),
        category=str(category).strip(),
        url=urljoin(config.homepage, str(link)),
        icon=urljoin(config.homepage, str(icon)),
    )


def parse_page(page: str, config: SourceConfig) -> list[Programme]:
    found: dict[tuple[str, datetime, str], Programme] = {}
    for blob in _json_blobs(page):
        for obj in _walk(blob):
            programme = _programme_from_object(obj, config)
            if programme:
                found[(programme.channel_id, programme.start, programme.title)] = programme

    if not found:
        soup = BeautifulSoup(page, "html.parser")
        for node in soup.select("[data-channel], [data-canal]"):
            obj = dict(node.attrs)
            obj["title"] = node.get("data-title") or node.get_text(" ", strip=True)
            programme = _programme_from_object(obj, config)
            if programme:
                found[(programme.channel_id, programme.start, programme.title)] = programme

    return sorted(found.values(), key=lambda item: (item.start, item.channel_id, item.title))


class Adapter:
    def fetch_and_parse(self, config: SourceConfig) -> list[Programme]:
        guide_url = str(config.options.get("guide_url", config.homepage))
        return parse_page(_fetch(guide_url), config)
