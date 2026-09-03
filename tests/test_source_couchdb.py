import os
import unittest
from unittest.mock import patch

from sirs_postgre.source.couchdb import CouchDBClient, CouchDBConfig, connect_couchdb


class FakeResponse:
    def __init__(self, payload=None, *, content=b"", status_code=200):
        self.payload = payload
        self.content = content
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("Réponse HTTP inattendue dans le test")


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return next(self.responses)


class CouchDBInfrastructureTest(unittest.TestCase):
    def make_client(self, responses):
        session = FakeSession(responses)
        config = CouchDBConfig(
            url="http://couch.test:5984/",
            database="sirs test",
            username="reader",
            password="secret",
        )
        return CouchDBClient(config, session=session), session

    def test_local_profile_has_no_hardcoded_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            config = CouchDBConfig.from_profile("local")
        self.assertEqual(config.database, "sirs_source")
        self.assertIsNone(config.auth)

    def test_connect_uses_compatible_profile_environment(self):
        environment = {
            "SIRS_PROFILE": "secure",
            "SIRS_SECURE_COUCHDB_URL": "https://couch.example.test",
            "SIRS_SECURE_DATABASE": "production",
            "SIRS_SECURE_USERNAME": "reader",
            "SIRS_SECURE_PASSWORD": "secret",
        }
        session = FakeSession([])
        with patch.dict(os.environ, environment, clear=True):
            client = connect_couchdb(session=session)
        self.assertEqual(client.config.profile, "secure")
        self.assertIs(client.session, session)

    def test_check_and_count_use_read_only_endpoints(self):
        client, session = self.make_client(
            [
                FakeResponse({"db_name": "sirs test", "doc_count": 12}),
                FakeResponse({"docs": [{"_id": "a"}, {"_id": "b"}]}),
            ]
        )
        status = client.check_connection()
        count = client.count_by_class("fr.sirs.core.model.Digue")
        self.assertEqual(status.document_count, 12)
        self.assertEqual(count, 2)
        self.assertEqual(session.calls[0][0], "GET")
        method, url, kwargs = session.calls[1]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://couch.test:5984/sirs%20test/_find")
        self.assertEqual(kwargs["json"]["fields"], ["_id"])

    def test_attachment_names_are_encoded(self):
        client, session = self.make_client([FakeResponse(content=b"photo")])
        content = client.get_attachment("doc/1", "photos/photo 1.jpg")
        self.assertEqual(content, b"photo")
        self.assertTrue(session.calls[0][1].endswith("/doc%2F1/photos%2Fphoto%201.jpg"))

    def test_database_info_reads_the_global_sirs_document(self):
        client, session = self.make_client(
            [
                FakeResponse(
                    {
                        "_id": "$sirs",
                        "epsgCode": "EPSG:3950",
                        "crsWkt": "PROJCS[\"RGF93 / CC50\"]",
                        "proj4": "+proj=lcc",
                    }
                )
            ]
        )
        info = client.get_database_info()
        self.assertEqual(info.source_database, "sirs test")
        self.assertEqual(info.epsg_code, "EPSG:3950")
        self.assertIn("RGF93 / CC50", info.crs_wkt)
        self.assertTrue(session.calls[0][1].endswith("/%24sirs"))


if __name__ == "__main__":
    unittest.main()
