import re
from src.config import settings

def test_cors_regex():
    regex = settings.CORS_ALLOWED_ORIGIN_REGEX
    assert regex is not None, "CORS_ALLOWED_ORIGIN_REGEX should not be None"
    
    pattern = re.compile(regex)
    
    target_url = "https://app-evangelista-frontend.jollyflower-774ba306.eastus2.azurecontainerapps.io"
    assert pattern.match(target_url), f"Regex {regex} failed to match {target_url}"
    print(f"Success: {target_url} matched by {regex}")

if __name__ == "__main__":
    test_cors_regex()
