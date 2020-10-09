"""
This module defines all the needed classes for storing the
information for all the different CM's searches.
"""
import os
from abc import ABC, abstractmethod
from typing import List
from flask import jsonify
from lxml import html
import html as h

import requests

from app.core.common.helpers import (
    datetime_from_string,
    send_post_then_get_html_string,
    normalize_str,
)
from .cm_news import CMNews


class CMSearch(ABC):
    """Base model to store CM search news"""

    login_payload = {"username": os.getenv("CM_USER"), "password": os.getenv("CM_PW")}
    login_url = "https://aminhaconta.xl.pt/LoginNonio?returnUrl=https%3a%2f%2fwww.cmjornal.pt%2f&isLayer=1&siteHost=www.cmjornal.pt"

    _found_news: List[CMNews]

    def __init__(self):
        self._found_news = []

    # __________________________________________________________________________________________________________________________

    @property
    def found_news(self):
        return self._found_news

    # __________________________________________________________________________________________________________________________

    @found_news.setter
    def found_news(self, value):
        self._found_news = value

    # __________________________________________________________________________________________________________________________

    @abstractmethod
    def search(self, obj: any) -> None:
        "Child classes must implement 'search' method in order to implement their custom logic of adding news to the news list"

    # __________________________________________________________________________________________________________________________

    @abstractmethod
    def serialize_to_json(self) -> str:
        "Child classes must implement 'serialize_to_json' method in order to implement their custom logic of serializing themselves to JSON format"


class CMTopicSearch(CMSearch):
    def __init__(self, topic: str, start_date: str, end_date: str) -> None:
        super().__init__()
        self.topic = topic
        self.start_date = datetime_from_string(start_date)
        self.end_date = datetime_from_string(end_date)

    def serialize_to_json(self) -> str:
        """ Serializes Keywords Search object to json"""
        return jsonify(
            {
                "topic": self.topic,
                "start date": self.start_date.strftime("%d/%m/%Y"),
                "end date": self.end_date.strftime("%d/%m/%Y"),
                "number of found news": str(len(self.found_news)),
                "news": list(map(lambda x: x.serialize_to_json(), self.found_news)),
            }
        )

    def search(self) -> None:
        index = 0
        full_stop = False

        while True:
            html_string = requests.get(
                f"https://www.cmjornal.pt/mais-sobre/loadmore?friendlyUrl=mais-sobre&urlRefParameters=?ref=Mais%20Sobre_BlocoMaisSobre&contentStartIndex={index}&searchKeywords={self.topic.replace(' ', '-')}"
            ).text

            if html_string in ["\r\n", ""]:
                break

            tree = html.fromstring(html_string)
            for article in tree.xpath("//article"):

                url = article.xpath(".//h2/a")[0].attrib["data-name"]
                # Make sure URL is correct. Check if it's not a href
                url = "https://www.cmjornal.pt" + url if url[0] == "/" else url
                # Discard url junk
                url = url.split("?ref")[0]
                # If news is of type 'interativa', 'multimedia' or 'perguntas' skip it
                if any(x in url for x in ["interativa", "multimedia", "perguntas"]):
                    continue

                news_date = datetime_from_string(
                    article.xpath('.//span[@class="dateTime"]')[0].text.replace("|", "")
                )

                if not (self.start_date < news_date < self.end_date):
                    continue

                description = article.xpath('.//span[@class="lead"]')[0].text

                # Read news html
                response = send_post_then_get_html_string(
                    self.login_url, self.login_payload, url
                )
                # Check if news still exists, if not skip it
                if response.status_code != 200:
                    continue
                # Build html tree
                tree = html.fromstring(response.text)
                # Get if news is opinion article from url
                is_opinion = "opiniao" in url
                # Get news section from url and capitalize it
                rubric = url.split("/")[3].capitalize()
                # Get authors info
                authors = tree.xpath("//span[@class='autor']//span")
                authors = authors[0].text if len(authors) != 0 else authors
                # Get text
                title = tree.xpath("//div[@class='centro']//section//h1")[0].text
                title = normalize_str(title)
                text = tree.xpath(
                    "//div[@class='texto_container paywall']//text()[not(ancestor::aside)][not(ancestor::div[@class='inContent'])][not(ancestor::blockquote)]"
                )
                # Remove '\n', '\r', and '\'
                text = normalize_str(" ".join(text))
                text = h.unescape(text)
                # Remove ads in case they exist
                text = text.split("Para aceder a todos os Exclusivos CM")[0]
                news = CMNews(
                    title,
                    description,
                    url,
                    rubric,
                    news_date,
                    [authors],
                    is_opinion,
                    text,
                )

                self.found_news.append(news)

            # Check for full stop
            if full_stop:
                break
            index += 6

        return self.found_news