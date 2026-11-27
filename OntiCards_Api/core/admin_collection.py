"""The shared Weaviate contract for account collections."""

import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from core.admin_bootstrap import AdminBootstrapError


class CollectionContractError(AdminBootstrapError):
    pass


def _request(base_url, path, *, method="GET", body=None, timeout=8):
    data = None if body is None else json.dumps(body).encode("utf-8")
    try:
        request = Request(base_url.rstrip("/") + path, data=data, method=method,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
            if len(payload) > 2 * 1024 * 1024:
                raise ValueError("collection definition too large")
            return response.status, json.loads(payload) if payload else None
    except HTTPError as error:
        return error.code, None
    except (URLError, OSError, ValueError):
        raise AdminBootstrapError("Weaviate is unavailable; collection sync is pending.") from None


def check_weaviate_ready(base_url, *, timeout):
    if _request(base_url, "/v1/.well-known/ready", timeout=timeout)[0] != 200:
        raise AdminBootstrapError("Weaviate is unavailable.")


def collection_definition(namespace, owner=None, claim=None):
    description = (
        "OntiCards administrator bootstrap owner " + owner if owner else "数据卡片存储"
    )
    properties = [
        {"name": name, "dataType": ["text"], "tokenization": tokenization,
         "indexFilterable": True, "indexSearchable": searchable}
        for name, tokenization, searchable in (
            ("doc_id", "whitespace", True), ("abstract", "word", True), ("datasource_id", "field", False),
        )
    ]
    if claim is not None:
        properties[0]["description"] = "onticards-bootstrap-binding:" + claim
    return {
        "class": namespace,
        "description": description,
        "properties": properties,
        "multiTenancyConfig": {"enabled": False},
        "vectorizer": "none",
        "vectorIndexType": "hnsw",
        "vectorIndexConfig": {"distance": "cosine"},
    }


def _schema_path(namespace):
    return "/v1/schema/" + quote(namespace, safe="")


def _validate_collection(actual, expected):
    if not isinstance(actual, dict):
        raise CollectionContractError("Weaviate collection could not be verified.")

    actual_name = actual.get("class")
    index = actual.get("vectorIndexConfig") or {}
    inverted = actual.get("invertedIndexConfig") or {}
    tenancy = actual.get("multiTenancyConfig") or {}
    properties = actual.get("properties") or []
    if (not all(isinstance(value, dict) for value in (index, inverted, tenancy))
            or not isinstance(properties, list)
            or not all(isinstance(prop, dict) and isinstance(prop.get("name"), str) for prop in properties)):
        raise CollectionContractError("Weaviate collection could not be verified.")
    bm25 = inverted.get("bm25") or {}
    stopwords = inverted.get("stopwords") or {}
    if (not isinstance(bm25, dict) or not isinstance(stopwords, dict)
            or not isinstance(bm25.get("k1", 1.2), (int, float))
            or any(not isinstance(index.get(kind) or {}, dict) for kind in ("pq", "bq", "sq", "rq"))):
        raise CollectionContractError("Weaviate collection could not be verified.")

    # Historical collections cannot mutate an existing property's description.
    # Reconciliation adds a dedicated, nonindexed property to the same collection.
    legacy_binding = [prop for prop in properties if prop["name"] == "onticards_binding"]
    expected_claim = expected["properties"][0].get("description")
    if legacy_binding:
        binding = legacy_binding[0]
        if (len(legacy_binding) != 1 or not expected_claim or binding.get("description") != expected_claim
                or binding.get("dataType") != ["text"] or binding.get("tokenization") != "field"
                or any(binding.get(flag, True) for flag in ("indexFilterable", "indexSearchable"))
                or binding.get("indexRangeFilters", False)):
            raise CollectionContractError("Weaviate collection ownership or schema does not match.")
        properties = [prop for prop in properties if prop["name"] != "onticards_binding"]

    if (
        not isinstance(actual_name, str)
        or actual_name.lower() != expected["class"].lower()
        or actual.get("description") != expected["description"]
        or actual.get("vectorizer") != "none"
        or actual.get("vectorIndexType") != "hnsw"
        or actual.get("vectorConfig")
        or any(tenancy.get(option, False) for option in ("enabled", "autoTenantCreation", "autoTenantActivation"))
        or index.get("distance") != "cosine"
        or index.get("skip", False)
        or any((index.get(kind) or {}).get("enabled") for kind in ("pq", "bq", "sq", "rq"))
        or bm25.get("b", 0.75) != 0.75 or abs(bm25.get("k1", 1.2) - 1.2) > 1e-6
        or stopwords.get("preset", "en") != "en"
        or stopwords.get("additions") or stopwords.get("removals")
        or any(inverted.get(flag) for flag in ("indexNullState", "indexPropertyLength", "indexTimestamps"))
        or len(properties) != len(expected["properties"])
    ):
        raise CollectionContractError("Weaviate collection ownership or schema does not match.")

    by_name = {prop["name"]: prop for prop in properties}
    for wanted in expected["properties"]:
        prop = by_name.get(wanted["name"], {})
        if any(prop.get(key) != value for key, value in wanted.items() if key != "description"):
            raise CollectionContractError("Weaviate collection ownership or schema does not match.")
        if prop.get("indexRangeFilters", False):
            raise CollectionContractError("Weaviate collection ownership or schema does not match.")
        if "description" in wanted:
            description = str(prop.get("description", ""))
            if legacy_binding and description.startswith("onticards-bootstrap-binding:"):
                raise CollectionContractError("Weaviate collection has conflicting binding evidence.")
            if not legacy_binding and not hmac.compare_digest(description.encode(), wanted["description"].encode()):
                raise CollectionContractError("Weaviate collection ownership or schema does not match.")


def verify_admin_collection(base_url, namespace, owner, claim, *, timeout=2):
    if not claim:
        raise CollectionContractError("Administrator collection has no verified claim.")
    status, actual = _request(base_url, _schema_path(namespace), timeout=timeout)
    if status != 200:
        raise CollectionContractError("Weaviate collection could not be verified.")
    _validate_collection(actual, collection_definition(namespace, owner, claim))


def inspect_existing_binding(base_url, namespace, owner, claim=None):
    path = _schema_path(namespace)
    status, actual = _request(base_url, path)
    if status != 200 or not isinstance(actual, dict) or not isinstance(actual.get("properties"), list):
        raise CollectionContractError("The original collection is unavailable.")
    expected = collection_definition(namespace, owner)
    if any(prop.get("name") == "onticards_binding" or
           str(prop.get("description", "")).startswith("onticards-bootstrap-binding:")
           for prop in actual.get("properties", [])):
        if not claim:
            raise CollectionContractError("The collection has unrecognized binding evidence.")
        verify_admin_collection(base_url, namespace, owner, claim)
        return True, actual["class"]
    _validate_collection(actual, expected)
    return False, actual["class"]


def bind_existing_account_collection(base_url, namespace, owner, claim):
    already_bound, canonical_name = inspect_existing_binding(base_url, namespace, owner, claim)
    if not already_bound:
        status, _ = _request(base_url, _schema_path(canonical_name) + "/properties", method="POST", body={
            "name": "onticards_binding", "description": "onticards-bootstrap-binding:" + claim,
            "dataType": ["text"], "tokenization": "field", "indexFilterable": False,
            "indexSearchable": False,
        })
        if status not in (200, 201):
            raise CollectionContractError("The original collection could not be rebound.")
    verify_admin_collection(base_url, namespace, owner, claim)


def ensure_account_collection(base_url, namespace, owner=None, claim=None):
    """Provision only a missing collection and verify every successful result."""
    expected = collection_definition(namespace, owner, claim)
    path = _schema_path(namespace)
    status, actual = _request(base_url, path)
    if status == 404:
        status, _ = _request(base_url, "/v1/schema", method="POST", body=expected)
        if status not in (200, 201, 409, 422):
            raise AdminBootstrapError("Weaviate collection creation is pending.")
        status, actual = _request(base_url, path)
    if status != 200:
        raise CollectionContractError("Weaviate collection could not be verified.")
    _validate_collection(actual, expected)


def account_field_index_marker(owner, claim):
    return f"OntiCards account field index {owner} {claim}"


def delete_owned_account_collection(base_url, namespace, owner, claim):
    """Check independent metadata for every collection before sending deletes."""
    main, fields = _schema_path(namespace), _schema_path(namespace + "__field_index")
    main_status, actual = _request(base_url, main)
    fields_status, index = _request(base_url, fields)
    if main_status not in (200, 404) or fields_status not in (200, 404):
        raise AdminBootstrapError("Collection cleanup is pending.")
    if not claim and 200 in (main_status, fields_status):
        raise CollectionContractError("Collection cleanup requires trusted ownership evidence.")
    if main_status == 200:
        _validate_collection(actual, collection_definition(namespace, owner, claim))
    if fields_status == 200 and (
        not isinstance(index, dict) or index.get("description") != account_field_index_marker(owner, claim)
    ):
        raise CollectionContractError("Field index cleanup requires trusted ownership evidence.")
    for path, status in ((fields, fields_status), (main, main_status)):
        if status == 200 and _request(base_url, path, method="DELETE")[0] not in (200, 204, 404):
            raise AdminBootstrapError("Collection cleanup is pending.")
        if _request(base_url, path)[0] != 404:
            raise AdminBootstrapError("Collection cleanup is pending.")
