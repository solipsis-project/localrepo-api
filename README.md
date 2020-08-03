Python module to implement API-like functionality for the FurAffinity.net website

## Requirements

This module requires the following pypi modules:<br>
* [beautifulsoup4](https://www.crummy.com/software/BeautifulSoup/)
* [cfscrape](https://github.com/Anorov/cloudflare-scrape)
* [lxml](https://github.com/lxml/lxml/)
* [requests](https://github.com/requests/requests)
* [python-dateutil](https://github.com/dateutil/dateutil/)

## Usage

The API is comprised of a main class `FAAPI` and two submission classes: `Sub` and `SubPartial`.
Once `FAAPI` is initialized its method can be used to crawl FA and return machine-readable objects.

```python
import faapi
import json

api = faapi.FAAPI()
sub, sub_file = api.get_sub(12345678, get_file=True)

print(sub.id, sub.title, sub.author, f"{len(sub_file)/1024:02f}KiB")

with open(f"{sub.id}.json", "w") as f:
    f.write(json.dumps(sub))

with open(sub.file_url.split("/")[-1], "wb") as f:
    f.write(sub_file)

gallery, _ = api.gallery("user_name", 1)
with open("user_name-gallery.json", "w") as f:
    f.write(json.dumps(gallery))
```

### Crawl Delay

### Cookies

To access protected pages, cookies from an active session are needed. These cookies must be given to the FAAPI object as a list of dictionaries, each containing a `name` and a `value` field. The cookies list should look like the following random example:

```python
cookies = [
    {"name": "a", "value": "38565475-3421-3f21-7f63-3d341339737"},
    {"name": "b", "value": "356f5962-5a60-0922-1c11-65003b703038"},
]
```

Only cookies `a` and `b` are needed.

To access session cookies, consult the manual of the browser used to login.

*Note:* it is important to not logout of the session the cookies belong, otherwise they will no longer work.

## FAAPI

This is the main object that handles all the calls to scrape pages and get submissions.

### Init

`__init__(cookies: List[dict] = None)`

The class init has a single optional argument `cookies` necessary to read logged-in-only pages.
The cookies can be omitted and the API will still be able to access public pages.

*Note:* Cookies must be in the format mentioned above in [#Cookies](#cookies).

### Methods

1. `get(url: str, **params) -> requests.Response`<br>
This returns a response object containing the result of the get operation on the given url with the optional `**params` added to it (url provided is considered as path from 'https://www.furaffinity.net/').

2. `get_parse(url: str, **params) -> bs4.BeautifulSoup`<br>
Similar to `get()` but returns the parsed  HTML from the normal get operation.

3. `get_sub(sub_id: Union[int, str], get_file: bool = False) -> Tuple[Sub, Optional[bytes]]`<br>
Given a submission ID in either int or str format, it returns a `Sub` object containing the various metadata of the submission itself and a `bytes` object with the submission file if `get_file` is passed as `True`.

4. `get_sub_file(sub: Sub) -> Optional[bytes]`<br>
Given a submission object, it downloads its file and returns it as a `bytes` object.

5. `userpage(user: str) -> Tuple[str, str, bs4.BeautifulSoup]`<br>
Returns the user's full display name - i.e. with capital letters and extra characters such as "_" -, the user's status - the first character found beside the user name - and the parsed profile text in HTML.

6. `gallery(user: str, page: int = 1) -> Tuple[List[SubPartial], int]`<br>
Returns the list of submissions found on a specific gallery page and the number of the next page. The returned page number is set to 0 if it is the last page.

7. `scraps(user: str, page: int = 1) -> -> Tuple[List[SubPartial], int]`<br>
Same as `gallery()`, but scrapes a user's scraps page instead.

8. `favorites(user: str, page: str = '') -> Tuple[List[SubPartial], str]`<br>
As `gallery()` and `scraps()` it downloads a user's favorites page. Because of how favorites pages work on FA, the `page` argument (and the one returned) are strings. If the favorites page is the last then an empty string is returned as next page. An empty page value as argument is equivalent to page 1.<br>
*Note:* favorites page "numbers" do not follow any scheme and are only generated server-side.

9. `search(q: str = '', page: int = 0, **params) -> Tuple[List[SubPartial], int, int, int, int]`<br>
Parses FA search given the query (and optional other params) and returns the submissions found and the next page together with basic search statistics: the number of the first submission in the page, the number of the last submission in the page (0-indexed), and the total number of submissions found in the search. For example if the the last three returned integers are 1, 47 and 437, then the the page contains submissions 1 through 48 of a search that has found a total of 437 submissions.

## SubPartial

This lightweight submission object is used to contain the information gathered when parsing gallery, scraps, favorites and search pages. It contains only the following fields:

* `id` submission id
* `title` submission title
* `author` submission author
* `rating` submission rating [general, mature, adult]
* `type` submission type [text, image, etc...]

`SubPartial` can be directly casted to a dict object or iterated through.

### Init

`__init__(figure_tag: bs4.element.Tag)`

`SubPartial` init needs a figure tag taken from a parsed page. This tag is not saved in the submission object.

### Methods

* `parse_figure_tag(figure_tag: bs4.element.Tag)`<br>
Takes a figure tag from a parsed page and parses it for information.

## Sub

The main class that parses and holds submission metadata.

* `id` submission id
* `title` submission title
* `author` submission author
* `date` upload date in YYYY-MM-DD format
* `tags` tags list
* `category` category \*
* `species` species \*
* `gender` gender \*
* `rating` rating \*
* `desc` the description as an HTML formatted string
* `file_url` the url to the submission file

\* these are extracted exactly as they appear on the submission page

`Sub` can be directly casted to a dict object and iterated through.

### Init

`__init__(self, sub_page: bs4.BeautifulSoup = None)`

To initialise the object, An optional `bs4.BeautifulSoup` object is needed containing the parsed HTML of a submission page.

The `sub_page` argument is saved as an instance variable and is then parsed to obtain the other fields.

If no `sub_page` is passed then the object fields will remain at their default - empty - value.

### Methods

* `parse_page()`<br>
Parses the stored submissions page for metadata.