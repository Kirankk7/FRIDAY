current_url = ""
current_title = ""
last_search = ""


def save_browser_state(
    url="",
    title="",
    search=""
):
    global current_url
    global current_title
    global last_search

    if url:
        current_url = url

    if title:
        current_title = title

    if search:
        last_search = search


def get_browser_state():

    return {

        "url":
        current_url,

        "title":
        current_title,

        "search":
        last_search
    }