"""Collection contract checks against an isolated Weaviate service."""

import os
import secrets
import unittest
from uuid import uuid4

from core.admin_collection import (
    CollectionContractError, _request, collection_definition,
    ensure_account_collection, verify_admin_collection,
)


WEAVIATE = "http://127.0.0.1:18188"


@unittest.skipUnless(os.environ.get("ONTICARDS_BOOTSTRAP_TEST_SOCKET"), "requires the private test stack")
class CollectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status, meta = _request(WEAVIATE, "/v1/meta")
        if status != 200 or meta["version"] != "1.36.0":
            raise RuntimeError("Expected the dedicated Weaviate 1.36.0 test service.")

    def fixture(self):
        name = "Onti55Contract" + uuid4().hex
        owner = uuid4().hex
        claim = secrets.token_hex(32)
        path = "/v1/schema/" + name
        self.addCleanup(lambda: _request(WEAVIATE, path, method="DELETE"))
        return name, owner, claim, path, collection_definition(name, owner, claim)

    def check_rejection(self, change):
        name, owner, claim, path, body = self.fixture()
        change(body)
        status, _ = _request(WEAVIATE, "/v1/schema", method="POST", body=body)
        self.assertIn(status, (200, 201), "The different fixture schema must be accepted by Weaviate.")
        status, before = _request(WEAVIATE, path)
        self.assertEqual(status, 200)
        with self.assertRaises(CollectionContractError):
            verify_admin_collection(WEAVIATE, name, owner, claim)
        with self.assertRaises(CollectionContractError):
            ensure_account_collection(WEAVIATE, name, owner, claim)
        self.assertEqual(_request(WEAVIATE, path), (200, before))

    def test_shared_contract_normal_and_bootstrap(self):
        name, owner, claim, _, _ = self.fixture()
        ensure_account_collection(WEAVIATE, name, owner, claim)
        verify_admin_collection(WEAVIATE, name, owner, claim)
        another = "Onti55Normal" + uuid4().hex
        self.addCleanup(lambda: _request(WEAVIATE, "/v1/schema/" + another, method="DELETE"))
        ensure_account_collection(WEAVIATE, another)
        _, actual = _request(WEAVIATE, "/v1/schema/" + another)
        self.assertEqual(len(actual["properties"]), 3)

    def test_properties_tokenization_and_indexes(self):
        def different_type(body):
            prop = body["properties"][0]
            prop.update(dataType=["int"], indexSearchable=False)
            prop.pop("tokenization")

        changes = {
            "property set": lambda b: b["properties"].pop(),
            "data type": different_type,
            "tokenization": lambda b: b["properties"][0].update(tokenization="word"),
            "filter index": lambda b: b["properties"][0].update(indexFilterable=False),
            "search index": lambda b: b["properties"][0].update(indexSearchable=False),
            "BM25": lambda b: b.update(invertedIndexConfig={"bm25": {"b": 0.55, "k1": 1.2}}),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                self.check_rejection(change)

    def test_tenancy_named_vectors_hnsw_and_distance(self):
        def named_vectors(body):
            for key in ("vectorizer", "vectorIndexType", "vectorIndexConfig"):
                body.pop(key)
            body["vectorConfig"] = {"alternate": {"vectorizer": {"none": {}}, "vectorIndexType": "hnsw",
                                                    "vectorIndexConfig": {"distance": "cosine"}}}

        changes = {
            "tenancy": lambda b: b.update(multiTenancyConfig={"enabled": True}),
            "named vector": named_vectors,
            "index type": lambda b: b.update(vectorIndexType="flat"),
            "unindexed vectors": lambda b: b["vectorIndexConfig"].update(skip=True),
            "distance": lambda b: b["vectorIndexConfig"].update(distance="l2-squared"),
        }
        for label, change in changes.items():
            with self.subTest(label=label):
                self.check_rejection(change)

    def test_owner_and_claim_must_each_match(self):
        self.check_rejection(lambda b: b.update(description="Other owner"))
        self.check_rejection(lambda b: b["properties"][0].update(description="Unbound claim"))

    def test_incompatible_vectorizer(self):
        self.check_rejection(lambda b: b.update(vectorizer="text2vec-openai"))


if __name__ == "__main__":
    unittest.main()
