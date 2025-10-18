from ...abstraction.database_service import DatabaseService
import sqlite3

class SqliteService(DatabaseService):

    def __init__(self, key: str):
        super().__init__(name="SQlite Service", connection_string=key)

    def connect(self):
        self._connection = sqlite3.connect(self._connection_string)

    def disconnect(self):
        if self._connection:
            self._connection.close()
            self._connection = None

    def execute(self, script: str):
        if not self._connection:
            raise Exception("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute(script)
        self._connection.commit()
        return cursor.fetchall()