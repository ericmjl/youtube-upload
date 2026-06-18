"""YouTube video category helpers."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import urlopen

URL = "https://www.googleapis.com/youtube/v3/videoCategories"

# Static fallback map (category name -> id). Used by the CLI so that no network
# request is required to resolve a category. The ``get`` function below fetches
# the live, region-specific list when needed.
IDS = {
    "Film & Animation": 1,
    "Autos & Vehicles": 2,
    "Music": 10,
    "Pets & Animals": 15,
    "Sports": 17,
    "Short Movies": 18,
    "Travel & Events": 19,
    "Gaming": 20,
    "Videoblogging": 21,
    "People & Blogs": 22,
    "Comedy": 23,
    "Entertainment": 24,
    "News & Politics": 25,
    "Howto & Style": 26,
    "Education": 27,
    "Science & Technology": 28,
    "Nonprofits & Activism": 29,
    "Movies": 30,
    "Anime/Animation": 31,
    "Action/Adventure": 32,
    "Classics": 33,
    "Documentary": 35,
    "Drama": 36,
    "Family": 37,
    "Foreign": 38,
    "Horror": 39,
    "Sci-Fi/Fantasy": 40,
    "Thriller": 41,
    "Shorts": 42,
    "Shows": 43,
    "Trailers": 44,
}


def get(region_code="us", api_key=None):
    """Fetch the live category list for a region.

    :param region_code: ISO 3166-1 alpha-2 region code (default ``"us"``).
    :param api_key: optional YouTube Data API key.
    :returns: mapping of category title to category id.
    """
    params = dict(part="snippet", regionCode=region_code, key=api_key)
    full_url = f"{URL}?{urlencode(params)}"
    response = urlopen(full_url)
    categories_info = json.loads(response.read())
    items = categories_info["items"]
    return {item["snippet"]["title"]: item["id"] for item in items}
