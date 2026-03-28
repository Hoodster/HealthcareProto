import datetime as dt


class DummyService:
    @staticmethod
    def dummy():
        """Returns a mock ChatOut object for testing"""
        return {
            "id": 1,
            "title": "Test Chat",
            "created_at": dt.datetime.now()
        }