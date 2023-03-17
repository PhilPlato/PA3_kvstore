import pickle
import os
from cryptography.fernet import Fernet


class SymmetricKeyGenerator:
    def __init__(self):
        self.key = None

    def getmyKey(self):
        return self.key

    def generate_key(self):
        self.key = Fernet.generate_key()
        return self.key

    @classmethod
    def read(cls, filename):
        try:
            with open(filename, "rb") as f:
                return pickle.load(f)
        except FileNotFoundError as e:
            print(e)
            return cls()

    def write(self, filename: str):
        if not os.path.exists(filename):
            open(filename, "w").close()
        with open(filename, "wb") as f:
            pickle.dump(self, f)