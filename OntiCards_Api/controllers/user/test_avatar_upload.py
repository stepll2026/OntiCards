"""Isolated HTTP regression tests; no application services or credentials needed.

Run: python controllers/user/test_avatar_upload.py
The production avatar section is compiled unchanged into a Flask test app.
Only user lookup and commit are replaced with in-memory fakes.
"""
import ast
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid

from flask import Flask, request
from flask_restful import Api, Resource


class AvatarUploadTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).with_name("userManagement.py")
        source = path.read_text(encoding="utf-8")
        # Parse the entire module first: an invalid module cannot start the API.
        tree = ast.parse(source, filename=str(path))
        start = source.index("# ==================== 用户头像上传配置")
        end = source.index("# 获取所有用户信息接口", start)
        nodes = [n for n in tree.body if start <= sum(len(s) for s in source.splitlines(True)[:n.lineno - 1]) < end]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.user = SimpleNamespace(avatar="original")
        self.commits = 0

        def commit():
            self.commits += 1

        def lookup(**kwargs):
            return SimpleNamespace(first=lambda: self.user if kwargs.get("id") == "test-user" else None)

        ns = dict(os=os, uuid=uuid, __file__=str(path), Resource=Resource, request=request,
                  User=SimpleNamespace(query=SimpleNamespace(filter_by=lookup)),
                  db=SimpleNamespace(session=SimpleNamespace(commit=commit)))
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
        ns["UPLOAD_FOLDER"] = self.tmp.name
        self.ns = ns
        app = Flask(__name__)
        app.config["TESTING"] = True
        Api(app).add_resource(ns["UploadAvatarAPI"], "/avatar")
        self.client = app.test_client()

    def upload(self, method, filename="avatar.png", content=b"image", user="test-user"):
        data = {"user_id": user}
        if filename is not None:
            data["file"] = (io.BytesIO(content), filename)
        response = self.client.open("/avatar", method=method, data=data, content_type="multipart/form-data")
        response.request.close()
        response.request.input_stream.close()
        return response

    def test_normal_and_traversal_uploads_stay_in_directory(self):
        for method in ("POST", "PUT"):
            for name in ("avatar.png", "../../tmp/x.png", "..\\..\\x.JPG", "/tmp/x.gif", "头像.jpeg"):
                with self.subTest(method=method, name=name):
                    response = self.upload(method, name)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json["code"], 200)
                    saved = response.json["data"]["avatar_url"].rsplit("/", 1)[1]
                    self.assertRegex(saved, r"^[0-9a-f]{32}\.(png|jpg|gif|jpeg)$")
                    self.assertEqual(Path(self.tmp.name, saved).read_bytes(), b"image")
                    self.assertEqual(self.user.avatar, response.json["data"]["avatar_url"])

    def test_oversize_is_http_413_without_write_or_commit(self):
        for method in ("POST", "PUT"):
            with self.subTest(method=method):
                response = self.upload(method, content=b"x" * (10 * 1024 * 1024 + 1))
                self.assertEqual(response.status_code, 413)
                self.assertEqual(response.json["code"], 413)
                self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
                self.assertEqual(self.commits, 0)
                self.assertEqual(self.user.avatar, "original")

    def test_exact_limit_is_saved_completely(self):
        for method in ("POST", "PUT"):
            with self.subTest(method=method):
                payload = b"x" * (10 * 1024 * 1024)
                response = self.upload(method, content=payload)
                self.assertEqual(response.json["code"], 200)
                saved = response.json["data"]["avatar_url"].rsplit("/", 1)[1]
                self.assertEqual(Path(self.tmp.name, saved).read_bytes(), payload)

    def test_invalid_requests_do_not_write(self):
        for method in ("POST", "PUT"):
            for name in (None, "", "bad.txt", "..", "/", "\\"):
                with self.subTest(method=method, name=name):
                    response = self.upload(method, name)
                    self.assertEqual(response.json["code"], 400)
                    self.assertLess(response.status_code, 500)
            self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
            self.assertEqual(self.commits, 0)

    def test_missing_user_does_not_write(self):
        for method in ("POST", "PUT"):
            response = self.upload(method, user="missing")
            self.assertEqual(response.json["code"], 404)
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
        self.assertEqual(self.commits, 0)

    def test_sanitized_basename(self):
        for raw, expected in (("../../tmp/x.png", "x.png"), ("..\\tmp\\x.png", "x.png"),
                              ("a\x00.png", "a.png"), ("", "")):
            self.assertEqual(self.ns["_safe_filename"](raw), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
