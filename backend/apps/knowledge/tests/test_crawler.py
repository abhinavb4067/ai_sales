from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.knowledge.crawler import crawl_website


def _html_response(html, content_type="text/html"):
    response = MagicMock()
    response.text = html
    response.headers = {"Content-Type": content_type}
    response.status_code = 200
    response.raise_for_status = lambda: None
    return response


class CrawlWebsiteTests(TestCase):
    @patch("apps.knowledge.crawler.safe_get")
    def test_single_page_with_no_links(self, mock_safe_get):
        def fake_get(url, **kwargs):
            if url.endswith("robots.txt"):
                return MagicMock(status_code=404)
            return _html_response("<html><body><p>Hello world</p></body></html>")

        mock_safe_get.side_effect = fake_get

        result = crawl_website("https://example.com/", max_pages=5)
        self.assertIn("Hello world", result)
        self.assertIn("https://example.com", result)

    @patch("apps.knowledge.crawler.safe_get")
    def test_follows_same_origin_links_and_dedupes(self, mock_safe_get):
        pages = {
            "https://example.com": "<a href='/about'>About</a><a href='/about'>Dup</a><p>Home page</p>",
            "https://example.com/about": "<p>About page</p>",
        }

        def fake_get(url, **kwargs):
            if url.endswith("robots.txt"):
                return MagicMock(status_code=404)
            return _html_response(pages.get(url.rstrip("/"), "<p>missing</p>"))

        mock_safe_get.side_effect = fake_get

        result = crawl_website("https://example.com", max_pages=5)
        self.assertIn("Home page", result)
        self.assertIn("About page", result)
        # /about requested only once despite two links to it
        about_calls = [c for c in mock_safe_get.call_args_list if c.args and "about" in c.args[0]]
        self.assertEqual(len(about_calls), 1)

    @patch("apps.knowledge.crawler.safe_get")
    def test_does_not_follow_offsite_links(self, mock_safe_get):
        def fake_get(url, **kwargs):
            if url.endswith("robots.txt"):
                return MagicMock(status_code=404)
            if url.rstrip("/") == "https://example.com":
                return _html_response("<a href='https://other.com/page'>Offsite</a><p>Home</p>")
            raise AssertionError(f"Should never fetch offsite URL: {url}")

        mock_safe_get.side_effect = fake_get

        result = crawl_website("https://example.com", max_pages=5)
        self.assertIn("Home", result)

    @patch("apps.knowledge.crawler.safe_get")
    def test_respects_robots_disallow(self, mock_safe_get):
        robots_txt = "User-agent: *\nDisallow: /private"

        def fake_get(url, **kwargs):
            if url.endswith("robots.txt"):
                return MagicMock(status_code=200, text=robots_txt)
            if url.rstrip("/") == "https://example.com":
                return _html_response("<a href='/private'>Private</a><p>Home</p>")
            if "private" in url:
                raise AssertionError("Should never fetch a robots.txt-disallowed URL")
            return _html_response("<p>unused</p>")

        mock_safe_get.side_effect = fake_get

        result = crawl_website("https://example.com", max_pages=5)
        self.assertIn("Home", result)
        self.assertEqual(result.count("--- Page:"), 1)  # /private was never fetched as a page

    @patch("apps.knowledge.crawler.safe_get")
    def test_max_pages_is_capped(self, mock_safe_get):
        def fake_get(url, **kwargs):
            if url.endswith("robots.txt"):
                return MagicMock(status_code=404)
            page_num = url.rstrip("/").split("/")[-1] or "0"
            next_num = int(page_num) + 1 if page_num.isdigit() else 1
            return _html_response(f"<a href='/{next_num}'>Next</a><p>Page {page_num}</p>")

        mock_safe_get.side_effect = fake_get

        result = crawl_website("https://example.com", max_pages=3)
        self.assertEqual(result.count("--- Page:"), 3)

    @patch("apps.knowledge.crawler.safe_get", side_effect=Exception("network down"))
    def test_unreachable_start_page_returns_empty_string(self, mock_safe_get):
        result = crawl_website("https://example.com", max_pages=5)
        self.assertEqual(result, "")
