class Annotator:
    def __init__(self, master, sentences, categories):
        self.master = master
        self.sentences = sentences
        self.categories = categories

    # def save_annotations(self, fileName):
    #     with open(fileName, 'w', encoding='utf-8') as file:
    #         json.dump(data)