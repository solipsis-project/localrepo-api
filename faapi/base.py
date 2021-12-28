from http.cookiejar import CookieJar
from time import perf_counter
from time import sleep
from typing import Any
from typing import Optional
from typing import Union
from urllib.robotparser import RobotFileParser

from .connection import CloudflareScraper
from .connection import Response
from .connection import get
from .connection import get_robots
from .connection import join_url
from .connection import make_session
from .connection import stream_binary
from .exceptions import CrawlDelayError
from .exceptions import DisallowedPath
from .exceptions import Unauthorized
from .journal import Journal
from .parse import BeautifulSoup
from .parse import check_page
from .parse import check_page_raise
from .parse import parse_loggedin_user
from .parse import parse_page
from .parse import parse_search_submissions
from .parse import parse_user_favorites
from .parse import parse_user_journals
from .parse import parse_user_submissions
from .parse import parse_watchlist
from .parse import username_url
from .submission import Submission
from .submission import SubmissionPartial
from .user import User
from .user import UserPartial


class FAAPI:
    def __init__(self, cookies: Union[list[dict[str, str]], CookieJar] = None):
        self.session: CloudflareScraper = make_session(cookies or [])
        self.robots: RobotFileParser = get_robots(self.session)
        self.last_get: float = perf_counter() - self.crawl_delay
        self.raise_for_delay: bool = False
        self.raise_for_unauthorized: bool = True

    @property
    def user_agent(self) -> str:
        return self.session.headers["User-Agent"]

    @property
    def crawl_delay(self) -> float:
        return float(self.robots.crawl_delay(self.user_agent) or 1)

    def load_cookies(self, cookies: Union[list[dict[str, str]], CookieJar]):
        self.session = make_session(cookies)

    def handle_delay(self):
        if (delay_diff := perf_counter() - self.last_get) < self.crawl_delay:
            if self.raise_for_delay:
                raise CrawlDelayError(f"Crawl-delay not respected {delay_diff}<{self.crawl_delay}")
            sleep(self.crawl_delay - delay_diff)
        self.last_get = perf_counter()

    def check_path(self, path: str, *, raise_for_disallowed: bool = True) -> bool:
        if not (allowed := self.robots.can_fetch(self.user_agent, path)) and raise_for_disallowed:
            raise DisallowedPath(f"Path {path} is not allowed by robots.txt")
        return allowed

    @property
    def connection_status(self) -> bool:
        try:
            return self.get("/").ok
        except ConnectionError:
            return False

    @property
    def login_status(self) -> bool:
        return parse_loggedin_user(self.get_parsed("login", skip_auth_check=True)) is not None

    def get(self, path: str, **params) -> Response:
        self.check_path(path)
        self.handle_delay()
        return get(self.session, path, **params)

    def get_parsed(self, path: str, *, skip_page_check: bool = False, skip_auth_check: bool = False, **params
                   ) -> BeautifulSoup:
        response: Response = self.get(path, **params)
        response.raise_for_status()
        page: BeautifulSoup = parse_page(response.text)
        if not skip_page_check:
            check_page_raise(page)
        if not skip_auth_check and self.raise_for_unauthorized and not parse_loggedin_user(page):
            raise Unauthorized("Not logged in")
        return page

    def me(self) -> Optional[User]:
        return self.user(user) if (user := parse_loggedin_user(self.get_parsed("login"))) else None

    def submission(self, submission_id: int, get_file: bool = False, *, chunk_size: int = None
                   ) -> tuple[Submission, Optional[bytes]]:
        sub: Submission = Submission(self.get_parsed(join_url("view", int(submission_id))))
        sub_file: Optional[bytes] = self.submission_file(sub, chunk_size=chunk_size) if get_file and sub.id else None
        return sub, sub_file

    def submission_file(self, submission: Submission, *, chunk_size: int = None) -> bytes:
        self.handle_delay()
        return stream_binary(self.session, submission.file_url, chunk_size=chunk_size)

    def journal(self, journal_id: int) -> Journal:
        return Journal(self.get_parsed(join_url("journal", int(journal_id))))

    def user(self, user: str) -> User:
        return User(self.get_parsed(join_url("user", username_url(user))))

    # noinspection DuplicatedCode
    def gallery(self, user: str, page: int = 1) -> tuple[list[SubmissionPartial], int]:
        page_parsed: BeautifulSoup = self.get_parsed(join_url("gallery", username_url(user), int(page)))
        info_parsed: dict[str, Any] = parse_user_submissions(page_parsed)
        for s in (submissions := list(map(SubmissionPartial, info_parsed["figures"]))):
            s.author.status, s.author.title, s.author.join_date, s.author.user_icon_url = [
                info_parsed["user_status"], info_parsed["user_title"],
                info_parsed["user_join_date"], info_parsed["user_icon_url"]
            ]
        return submissions, (page + 1) * (not info_parsed["last_page"])

    # noinspection DuplicatedCode
    def scraps(self, user: str, page: int = 1) -> tuple[list[SubmissionPartial], int]:
        page_parsed: BeautifulSoup = self.get_parsed(join_url("scraps", username_url(user), int(page)))
        info_parsed: dict[str, Any] = parse_user_submissions(page_parsed)
        for s in (submissions := list(map(SubmissionPartial, info_parsed["figures"]))):
            s.author.status, s.author.title, s.author.join_date, s.author.user_icon_url = [
                info_parsed["user_status"], info_parsed["user_title"],
                info_parsed["user_join_date"], info_parsed["user_icon_url"]
            ]
        return submissions, (page + 1) * (not info_parsed["last_page"])

    def favorites(self, user: str, page: str = "") -> tuple[list[SubmissionPartial], str]:
        page_parsed: BeautifulSoup = self.get_parsed(join_url("favorites", username_url(user), page.strip()))
        info_parsed: dict[str, Any] = parse_user_favorites(page_parsed)
        submissions: list[SubmissionPartial] = list(map(SubmissionPartial, info_parsed["figures"]))
        return submissions, info_parsed["next_page"]

    def journals(self, user: str, page: int = 1) -> tuple[list[Journal], int]:
        page_parsed: BeautifulSoup = self.get_parsed(join_url("journals", username_url(user), int(page)))
        info_parsed: dict[str, Any] = parse_user_journals(page_parsed)
        for j in (journals := list(map(Journal, info_parsed["sections"]))):
            j.author.name, j.author.status, j.author.title, j.author.join_date, j.author.user_icon_url = [
                info_parsed["user_name"], info_parsed["user_status"],
                info_parsed["user_title"], info_parsed["user_join_date"],
                info_parsed["user_icon_url"]
            ]
        return journals, (page + 1) * (not info_parsed["last_page"])

    def search(self, q: str, page: int = 1, **params) -> tuple[list[SubmissionPartial], int, int, int, int]:
        page_parsed: BeautifulSoup = self.get_parsed("search", q=q, page=(page := int(page)), **params)
        info_parsed: dict[str, Any] = parse_search_submissions(page_parsed)
        return (list(map(SubmissionPartial, info_parsed["figures"])), (page + 1) * (not info_parsed["last_page"]),
                info_parsed["from"], info_parsed["to"], info_parsed["total"])

    def watchlist_to(self, user: str, page: int = 1) -> tuple[list[UserPartial], int]:
        users: list[UserPartial] = []
        us, np = parse_watchlist(
            self.get_parsed(join_url("watchlist", "to", username_url(user), page), skip_auth_check=True))
        for s, u in us:
            user: UserPartial = UserPartial()
            user.name = u
            user.status = s
            users.append(user)
        return users, (page + 1) if np else 0

    def watchlist_by(self, user: str, page: int = 1) -> tuple[list[UserPartial], int]:
        users: list[UserPartial] = []
        us, np = parse_watchlist(
            self.get_parsed(join_url("watchlist", "by", username_url(user), page), skip_auth_check=True))
        for s, u in us:
            user: UserPartial = UserPartial()
            user.name = u
            user.status = s
            users.append(user)
        return users, (page + 1) if np else 0

    def user_exists(self, user: str) -> int:
        """
        0 okay
        1 account disabled
        2 system error
        3 unknown error
        4 request error
        """

        if not (res := self.get(join_url("user", username_url(user)))).ok:
            return 4
        elif (check := check_page(parse_page(res.text))) == 0:
            return 0
        elif check == 3:
            return 1
        elif check == 4:
            return 2
        else:
            return 3

    def submission_exists(self, submission_id: int) -> int:
        """
        0 okay
        1 account disabled
        2 system error
        3 unknown error
        4 request error
        """

        if not (res := self.get(join_url("view", submission_id))).ok:
            return 4
        elif (check := check_page(parse_page(res.text))) == 0:
            return 0
        elif check == 3:
            return 1
        elif check == 4:
            return 2
        else:
            return 3

    def journal_exists(self, journal_id: int) -> int:
        """
        0 okay
        1 account disabled
        2 system error
        3 unknown error
        4 request error
        """

        if not (res := self.get(join_url("journal", journal_id))).ok:
            return 4
        elif (check := check_page(parse_page(res.text))) == 0:
            return 0
        elif check == 3:
            return 1
        elif check == 4:
            return 2
        else:
            return 3
