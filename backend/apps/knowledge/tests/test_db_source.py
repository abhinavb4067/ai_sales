from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.knowledge.db_source import UnsafeDatabaseSourceError, fetch_rows_as_text


class ValidateConfigTests(TestCase):
    def test_rejects_unsupported_dialect(self):
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({"dialect": "oracle", "host": "db.example.com", "table": "products"})

    def test_rejects_missing_host(self):
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({"dialect": "postgresql", "table": "products"})

    def test_rejects_sql_injection_in_table_name(self):
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({
                "dialect": "postgresql", "host": "db.example.com", "table": "products; DROP TABLE users;",
            })

    def test_rejects_quoted_or_schema_qualified_table_name(self):
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({"dialect": "postgresql", "host": "db.example.com", "table": "public.products"})

    @patch("apps.knowledge.db_source.socket.getaddrinfo")
    def test_rejects_loopback_host(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("127.0.0.1", 0))]
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({"dialect": "postgresql", "host": "localhost", "table": "products"})

    @patch("apps.knowledge.db_source.socket.getaddrinfo")
    def test_rejects_cloud_metadata_host(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("169.254.169.254", 0))]
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({"dialect": "postgresql", "host": "metadata.internal", "table": "products"})

    @patch("apps.knowledge.db_source.socket.getaddrinfo")
    @override_settings(DATABASES={"default": {"HOST": "platform-db.internal"}})
    def test_rejects_platforms_own_database_host(self, mock_getaddrinfo):
        def fake_getaddrinfo(host, *args, **kwargs):
            ip = "10.0.0.5" if host in ("platform-db.internal", "customer-db.example.com") else "203.0.113.9"
            return [(2, 1, 6, "", (ip, 0))]

        mock_getaddrinfo.side_effect = fake_getaddrinfo
        with self.assertRaises(UnsafeDatabaseSourceError):
            fetch_rows_as_text({"dialect": "postgresql", "host": "customer-db.example.com", "table": "products"})

    @patch("apps.knowledge.db_source.socket.getaddrinfo")
    def test_allows_generic_private_ip_host(self, mock_getaddrinfo):
        # A business's own DB on their private network is a normal,
        # expected configuration — only loopback/metadata/platform-own-db
        # are blocked, not private ranges in general.
        mock_getaddrinfo.return_value = [(2, 1, 6, "", ("10.0.5.20", 0))]
        with patch("apps.knowledge.db_source._fetch_postgresql", return_value=(["id"], [(1,)])) as mock_fetch:
            result = fetch_rows_as_text({
                "dialect": "postgresql", "host": "db.internal.company.com", "database": "shop",
                "user": "ro_user", "password": "secret", "table": "products",
            })
        mock_fetch.assert_called_once()
        self.assertIn("id: 1", result)


class FetchRowsAsTextTests(TestCase):
    @patch("apps.knowledge.db_source.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("203.0.113.9", 0))])
    @patch("apps.knowledge.db_source._fetch_mysql")
    def test_mysql_dialect_dispatches_to_mysql_fetcher(self, mock_fetch_mysql, mock_getaddrinfo):
        mock_fetch_mysql.return_value = (["name", "price"], [("Widget", 9.99), ("Gadget", 19.99)])

        result = fetch_rows_as_text({
            "dialect": "mysql", "host": "mysql.example.com", "database": "shop",
            "user": "ro_user", "password": "secret", "table": "products",
        })

        self.assertIn("name: Widget", result)
        self.assertIn("price: 19.99", result)
        mock_fetch_mysql.assert_called_once()
