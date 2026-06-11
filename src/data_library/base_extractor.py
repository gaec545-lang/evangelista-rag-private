from abc import ABC, abstractmethod
import os
import requests

class BaseExtractor(ABC):
    def __init__(self, token_env_var=None, env_path=None):
        self.token = None
        if token_env_var and env_path:
            from dotenv import load_dotenv
            load_dotenv(env_path)
            self.token = os.environ.get(token_env_var)
    
    @abstractmethod
    def extract(self):
        pass
