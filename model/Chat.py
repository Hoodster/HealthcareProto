class Chat:

    def __init__(self, id, title=None, chat=None):
        self.id = id
        self.title = title or "New chat"
        self.chat = chat or []