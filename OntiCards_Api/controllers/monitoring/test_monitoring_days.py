"""Direct resource regressions using isolated request/ORM doubles.

Run: python3 -m unittest discover -s OntiCards_Api/controllers/monitoring -p test_monitoring_days.py -v
No application bootstrap, database, model, or credentials are required.
"""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


def load_api():
    dependencies = {}
    for name in ("flask", "flask_restful", "sqlalchemy",
                 "extensions.ext_database", "models.query_logs",
                 "models.query_stats_daily", "models.users"):
        dependencies[name] = ModuleType(name)
    dependencies["flask"].Blueprint = MagicMock()
    dependencies["flask"].request = SimpleNamespace(args={})
    dependencies["flask_restful"].Api = MagicMock()
    dependencies["flask_restful"].Resource = object
    for name in ("func", "case", "extract", "text"):
        setattr(dependencies["sqlalchemy"], name, MagicMock())
    dependencies["extensions.ext_database"].db = MagicMock()
    for name, cls in (("query_logs", "QueryLog"),
                      ("query_stats_daily", "QueryStatsDaily"), ("users", "User")):
        setattr(dependencies["models." + name], cls, MagicMock())
    spec = importlib.util.spec_from_file_location(
        "monitoring_under_test", Path(__file__).with_name("monitoring_api.py"))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, dependencies):
        spec.loader.exec_module(module)
    return module


class MonitoringDaysTests(unittest.TestCase):
    def setUp(self):
        self.api = load_api()
        self.uid = "00000000-0000-0000-0000-000000000001"
        self.api.QueryStatsDaily.stat_date.__ge__.return_value = True
        self.api.QueryLog.created_at.__ge__.return_value = True
        self.api.db.session.query.return_value.filter.return_value.first.return_value = (self.uid,)
        self.api.QueryStatsDaily.query.filter.return_value.order_by.return_value.all.return_value = []
        self.api.QueryLog.query.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

    def call(self, resource_name, days, user_id="valid"):
        args = {}
        if user_id == "valid":
            args["user_id"] = self.uid
        elif user_id is not None:
            args["user_id"] = user_id
        if days is not None:
            args["days"] = days
        self.api.request.args = args
        resource = getattr(self.api, resource_name)()
        # Only downstream analytics are replaced; execute the complete get method.
        for name in dir(resource):
            if name.startswith("_get_"):
                setattr(resource, name, MagicMock(return_value={}))
        return resource.get()

    def assert_days(self, name, key, supplied, expected):
        body, status = self.call(name, supplied)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["data"][key], expected)
        # Verify the database date boundary uses the same effective days.
        boundary = self.api.QueryStatsDaily.stat_date.__ge__.call_args.args[0]
        self.assertEqual(boundary, self.api.date.today() - self.api.timedelta(days=expected))

    def test_trend_defaults_for_missing_and_malformed(self):
        for value in (None, "", "abc", "1.5", "null", "9" * 5000):
            with self.subTest(value=str(value)[:20]):
                self.assert_days("MonitoringTrendResource", "days", value, 30)

    def test_performance_defaults_for_missing_and_malformed(self):
        for value in (None, "", "abc", "1.5", "null", "9" * 5000):
            with self.subTest(value=str(value)[:20]):
                self.assert_days("MonitoringPerformanceResource", "period_days", value, 7)

    def test_trend_valid_days_unchanged(self):
        for value in ("1", "7", "30", "31", "365", " 7 ", "+7", "0007"):
            with self.subTest(value=value):
                self.assert_days("MonitoringTrendResource", "days", value, int(value))

    def test_performance_valid_days_unchanged(self):
        for value in ("1", "7", "30", " 7 ", "+7", "0007"):
            with self.subTest(value=value):
                self.assert_days("MonitoringPerformanceResource", "period_days", value, int(value))

    def test_trend_out_of_range_keeps_existing_default(self):
        for value in ("0", "-1", "366", "999999999999999999999999999"):
            with self.subTest(value=value):
                self.assert_days("MonitoringTrendResource", "days", value, 30)

    def test_performance_out_of_range_keeps_existing_default(self):
        for value in ("0", "-1", "31", "365", "366", "999999999999999999999999999"):
            with self.subTest(value=value):
                self.assert_days("MonitoringPerformanceResource", "period_days", value, 7)

    def test_user_validation_still_runs_for_invalid_days(self):
        for name in ("MonitoringTrendResource", "MonitoringPerformanceResource"):
            for user_id in (None, "bad-uuid"):
                with self.subTest(resource=name, user_id=user_id):
                    self.api.db.session.query.reset_mock()
                    body, status = self.call(name, "abc", user_id)
                    self.assertEqual((body["code"], status), (400, 400))
                    self.api.db.session.query.assert_not_called()

    def test_unknown_user_is_still_404(self):
        self.api.db.session.query.return_value.filter.return_value.first.return_value = None
        for name in ("MonitoringTrendResource", "MonitoringPerformanceResource"):
            with self.subTest(resource=name):
                body, status = self.call(name, "abc")
                self.assertEqual((body["code"], status), (404, 404))

    def test_database_failure_is_still_500(self):
        self.api.db.session.query.side_effect = RuntimeError("synthetic failure")
        for name in ("MonitoringTrendResource", "MonitoringPerformanceResource"):
            with self.subTest(resource=name):
                body, status = self.call(name, "abc")
                self.assertEqual((body["code"], status), (500, 500))


if __name__ == "__main__":
    unittest.main()
