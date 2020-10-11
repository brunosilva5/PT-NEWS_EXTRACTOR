"""
This module defines all the needed classes for storing the
information for all the different Publico's searches.
"""
import os
import json
from abc import ABC, abstractmethod
from flask import jsonify
import requests

from app.core.common.helpers import datetime_from_string
from .publico_news import PublicoNews


class PublicoSearch(ABC):
    """Base model to store Publico search news"""

    _found_news: list[PublicoNews]

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
    def add_news(self, obj: any) -> None:
        "Child classes must implement 'add_news' method in order to implement their custom logic of adding news to the news list"

    # __________________________________________________________________________________________________________________________

    @abstractmethod
    def serialize_to_json(self) -> str:
        "Child classes must implement 'serialize_to_json' method in order to implement their custom logic of serializing themselves to JSON format"


class PublicoURLSearch(PublicoSearch):
    """ Model to store news from Publico's URL search """

    def __init__(self, *args, **kwargs) -> None:
        super(PublicoURLSearch, self).__init__(*args, **kwargs)

    # __________________________________________________________________________________________________________________________

    def add_news(self, url: str) -> None:
        """Adds a news to the found news list
        Parameters
        ----------
        url : str
            News URL to webscrape"""
        PublicoNews.validate_url(url)
        news_object = PublicoNews.build_from_url(url)
        if news_object not in self.found_news:
            self.found_news.append(news_object)

    # __________________________________________________________________________________________________________________________

    def serialize_to_json(self) -> None:
        """ Serializes URL Search object to JSON"""
        return jsonify(
            {
                "number of found news": str(len(self.found_news)),
                "news": list(map(lambda x: x.serialize_to_json(), self.found_news)),
            }
        )


# ______________________________________________________________________________________________________________________________


class PublicoAPISearch(PublicoSearch, ABC):
    """Base model to store news from Publico's API."""

    page_number: int
    login_payload = {
        "username": os.getenv("PUBLICO_USER"),
        "password": os.getenv("PUBLICO_PW"),
    }
    login_url = "https://www.publico.pt/api/user/login"
    base_api_url: str

    def __init__(self, start_date: str, end_date: str) -> None:
        super().__init__()
        self.page_number = 1
        self.start_date = datetime_from_string(start_date).date()
        self.end_date = datetime_from_string(end_date).date()

    @abstractmethod
    def consume_api(self) -> None:
        """Child classes must implement 'consume_api' method in order to implement their custom use of the Publico's API"""

    @property
    @abstractmethod
    def api_url(self):
        "Child classes must implement 'api_url' property in order to build their custom API URL"


class PublicoTopicSearch(PublicoAPISearch):
    """Model to store news from Publico's topic search """

    # __________________________________________________________________________________________________________________________

    def __init__(self, search_topic: str, start_date: str, end_date: str):
        super().__init__(start_date, end_date)
        self.search_topic = search_topic
        self.base_api_url = "https://www.publico.pt/api/list/"

    # __________________________________________________________________________________________________________________________

    def serialize_to_json(self) -> str:
        """ Serializes Topic Search object to json"""
        return jsonify(
            {
                "search topic": self.search_topic,
                "start date": self.start_date.strftime("%d/%m/%Y"),
                "end date": self.end_date.strftime("%d/%m/%Y"),
                "number of found news": str(len(self.found_news)),
                "news": list(map(lambda x: x.serialize_to_json(), self.found_news)),
            }
        )

    # __________________________________________________________________________________________________________________________

    def add_news(self, data: dict) -> None:
        """Adds a news to the found news list"""
        news_object = PublicoNews.deserialize_news(data)
        # check if object got deserialized, and if news does not already exist
        if isinstance(news_object, PublicoNews) and news_object not in self.found_news:
            self.found_news.append(news_object)

    # __________________________________________________________________________________________________________________________

    @property
    def api_url(self):
        return (
            self.base_api_url
            + self.search_topic.replace(" ", "-").lower()
            + "?page="
            + str(self.page_number)
        )

    # __________________________________________________________________________________________________________________________

    def consume_api(self):
        # Flag to stop search
        stop_entire_search = False

        while (r := requests.get(self.api_url).text) != "[]":
            print("Now reading page number {}...".format(self.page_number))
            # Read the json data
            data = json.loads(r)
            # iterate over each news dict and create a News object from it
            for item in data:
                # Found news out of lower bound date, STOP THE SEARCH!
                if PublicoNews.parse_date(item.get("data")) < self.start_date:
                    stop_entire_search = True
                    break  # stop the local search
                # Found news more recent that end date, SKIP AHEAD
                elif PublicoNews.parse_date(item.get("data")) > self.end_date:
                    continue
                # Found news inside the date rage, add to list
                else:
                    self.add_news(item)
            if stop_entire_search:
                break
            # Increment page
            self.page_number = self.page_number + 1

        print("Found {} news!".format(str(len(self.found_news))))


# ________________________________________________________________________________________________________________________________


class PublicoKeywordsSearch(PublicoAPISearch):
    """ Model to store news from Publico's keywords search """

    # __________________________________________________________________________________________________________________________

    def __init__(self, keywords: str, start_date: str, end_date: str) -> None:
        super().__init__(start_date, end_date)
        self.keywords = keywords
        self.base_api_url = "https://www.publico.pt/api/list/search/?query="

    # __________________________________________________________________________________________________________________________

    def serialize_to_json(self) -> str:
        """ Serializes Keywords Search object to json"""
        return jsonify(
            {
                "keywords": self.keywords,
                "start date": self.start_date.strftime("%d/%m/%Y"),
                "end date": self.end_date.strftime("%d/%m/%Y"),
                "number of found news": str(len(self.found_news)),
                "news": list(map(lambda x: x.serialize_to_json(), self.found_news)),
            }
        )

    # __________________________________________________________________________________________________________________________

    def add_news(self, data: dict) -> None:
        """Adds a news to the found news list"""
        news_object = PublicoNews.deserialize_news(data)
        # check if object got deserialized, and if news does not already exist
        if isinstance(news_object, PublicoNews) and news_object not in self.found_news:
            self.found_news.append(news_object)

    # __________________________________________________________________________________________________________________________

    @property
    def api_url(self):
        return (
            self.base_api_url
            + self.keywords.replace(" ", "%20").lower()
            + "&start="
            + self.start_date.strftime("%d-%m-%Y")
            + "&end="
            + self.end_date.strftime("%d-%m-%Y")
            + "&page="
            + str(self.page_number)
        )

    # __________________________________________________________________________________________________________________________

    def consume_api(self):

        while (r := requests.get(self.api_url).text) != "[]":
            print("Now reading page number {}...".format(self.page_number))
            # Read the json data
            data = json.loads(r)
            # iterate over each news dict and create a News object from it
            for item in data:
                self.add_news(item)
            # Increment page
            self.page_number = self.page_number + 1

        print("Found {} news!".format(str(len(self.found_news))))
