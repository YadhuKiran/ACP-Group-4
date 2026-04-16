import re
import scrapy


class GithubReposSpider(scrapy.Spider):
    name = "github_repos"
    allowed_domains = ["github.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    def __init__(self, username=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not username:
            raise ValueError("Please provide GitHub username: scrapy crawl github_repos -a username=YOUR_USERNAME")
        self.username = username
        self.start_urls = [f"https://github.com/{username}?tab=repositories"]

    def parse(self, response):
        """
        Parse the repositories list page.
        """
        repo_cards = response.css("li[itemprop='owns']")

        for repo in repo_cards:
            repo_relative_url = repo.css("a[itemprop='name codeRepository']::attr(href)").get()
            last_updated = (
                repo.css("relative-time::attr(datetime)").get()
                or repo.css("relative-time::text").get()
            )

            if repo_relative_url:
                yield response.follow(
                    repo_relative_url,
                    callback=self.parse_repo,
                    meta={"last_updated": last_updated}
                )

        # go to next page if repositories are paginated
        next_page = response.css("a[rel='next']::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_repo(self, response):
        """
        Parse each repository page.
        """
        repo_url = response.url
        repo_name = response.url.rstrip("/").split("/")[-1]
        last_updated = response.meta.get("last_updated")

        # About
        about = response.xpath("normalize-space(//*[@itemprop='about'])").get()

        # Detect empty repository
        page_text = " ".join(response.css("body *::text").getall())
        is_empty = "This repository is empty." in page_text

        if not about:
            if not is_empty:
                about = repo_name
            else:
                about = None

        # Languages
        if is_empty:
            languages = None
        else:
            langs = response.css("span[itemprop='programmingLanguage']::text").getall()
            if not langs:
                langs = response.xpath("//li[contains(@class,'d-inline')]//span[@itemprop='programmingLanguage']/text()").getall()
            langs = [lang.strip() for lang in langs if lang.strip()]
            languages = ", ".join(langs) if langs else None

        # Number of commits
        if is_empty:
            number_of_commits = None
        else:
            commit_text = response.xpath(
                "normalize-space(//a[contains(@href, '/commits/')])"
            ).get()

            if commit_text:
                match = re.search(r"([\d,]+)\s+commit", commit_text, re.IGNORECASE)
                number_of_commits = match.group(1) if match else None
            else:
                number_of_commits = None

        yield {
            "url": repo_url,
            "about": about,
            "last_updated": last_updated,
            "languages": languages,
            "number_of_commits": number_of_commits,
        }