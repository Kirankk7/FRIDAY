import requests
from bs4 import BeautifulSoup


def search_web(query):
    url = f"https://duckduckgo.com/html/?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    results = []

    for a in soup.select(".result__a")[:5]:
        results.append(a.get_text())

    return results