from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass

from bs4 import BeautifulSoup


KAKUYOMU_EPISODE_PATH = re.compile(r"^/works/[^/]+/episodes/[^/]+/?$")


@dataclass(slots=True)
class ExtractedWebParagraph:
    paragraph_id: str
    kind: str
    text: str


@dataclass(slots=True)
class KakuyomuEpisode:
    url: str
    work_title: str
    episode_title: str
    paragraphs: list[ExtractedWebParagraph]


def extract_kakuyomu_episode(url: str, *, timeout_seconds: int = 30) -> KakuyomuEpisode:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Expected an HTTP or HTTPS URL, got: {url}")
    if parsed.netloc not in {"kakuyomu.jp", "www.kakuyomu.jp"}:
        raise ValueError(f"Expected a kakuyomu.jp URL, got: {url}")
    if not KAKUYOMU_EPISODE_PATH.match(parsed.path):
        raise ValueError("Expected a Kakuyomu episode URL like /works/<work-id>/episodes/<episode-id>.")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/136.0 Safari/537.36"
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            html = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Kakuyomu returned HTTP {exc.code} for: {url}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Unable to access Kakuyomu URL: {url}") from exc

    soup = BeautifulSoup(html, "html.parser")
    work_title = _select_text(
        soup,
        [
            "#worksEpisodesEpisodeHeader-breadcrumbs li:first-child [itemprop='name']",
            "meta[property='og:title']",
        ],
    )
    episode_title = _select_text(
        soup,
        [
            ".widget-episodeTitle",
            "#worksEpisodesEpisodeHeader-breadcrumbs li:nth-child(2) [itemprop='name']",
        ],
    )
    if not work_title or not episode_title:
        raise ValueError("Unable to locate Kakuyomu work title or episode title on the page.")

    body = soup.select_one(".widget-episodeBody")
    if body is None:
        raise ValueError("Unable to locate Kakuyomu episode body on the page.")

    paragraphs: list[ExtractedWebParagraph] = [
        ExtractedWebParagraph(paragraph_id="web-p00001", kind="heading", text=episode_title)
    ]
    counter = 2
    for paragraph in body.find_all("p", recursive=False):
        classes = paragraph.get("class", [])
        if "blank" in classes:
            continue
        text = paragraph.get_text("", strip=True).strip()
        if not text:
            continue
        paragraphs.append(
            ExtractedWebParagraph(
                paragraph_id=f"web-p{counter:05d}",
                kind="paragraph",
                text=text,
            )
        )
        counter += 1

    if len(paragraphs) == 1:
        raise ValueError("No Kakuyomu episode paragraphs were extracted.")

    return KakuyomuEpisode(
        url=url,
        work_title=work_title,
        episode_title=episode_title,
        paragraphs=paragraphs,
    )


def _select_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            text = str(node.get("content", "")).strip()
        else:
            text = node.get_text("", strip=True).strip()
        if text:
            return text
    return ""
