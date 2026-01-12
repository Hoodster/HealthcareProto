import os
from openai import OpenAI

def load_dotenv(dotenv_path=".env"):
	try:
		with open(dotenv_path, "r") as f:
			for line in f:
				line = line.strip()
				if not line or line.startswith("#"):
					continue
				if "=" not in line:
					continue
				key, val = line.split("=", 1)
				key = key.strip()
				val = val.strip().strip('"').strip("'")
				if key and key not in os.environ:
					os.environ[key] = val
	except FileNotFoundError:
		pass

load_dotenv()

key = os.getenv("API_OPENAI")
client = OpenAI(api_key=key)
print(client.models.list())