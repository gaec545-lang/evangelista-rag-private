"""
ponytail: One runnable check to verify get_llm_client and FallbackLLMClient logic.
Run with: python Backend/tests/test_llm_clients.py
"""
import sys
import os
import asyncio

# ponytail: Ensure src is in python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.llm.factory import get_llm_client, FallbackLLMClient
from src.llm.base import LLMClient


class DummyClient(LLMClient):
    def __init__(self, name: str, should_fail: bool = False, response: str = "success"):
        self.name = name
        self.should_fail = should_fail
        self.response = response
        self.generate_calls = 0

    async def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.3, max_tokens: int = 2000) -> str:
        self.generate_calls += 1
        if self.should_fail:
            raise ValueError(f"Client {self.name} failed")
        return self.response

    async def embed(self, text: str) -> list[float]:
        if self.should_fail:
            raise ValueError(f"Client {self.name} embed failed")
        return [0.1, 0.2]


async def run_tests():
    print("Running LLM Clients & Fallback logic checks...")
    
    # 1. Test client caching
    client1 = get_llm_client()
    client2 = get_llm_client()
    assert client1 is client2, "get_llm_client should cache and return the exact same client instance"
    print("[OK] Client caching passed")

    # 2. Test FallbackLLMClient success on first attempt
    c1 = DummyClient("primary", should_fail=False, response="c1_response")
    c2 = DummyClient("fallback", should_fail=False, response="c2_response")
    fallback_client = FallbackLLMClient(c1, [c2])
    
    res = await fallback_client.generate("hello")
    assert res == "c1_response", f"Expected primary response, got {res}"
    assert c1.generate_calls == 1, "Primary client should have been called"
    assert c2.generate_calls == 0, "Fallback client should not have been called"
    print("[OK] FallbackLLMClient primary success passed")

    # 3. Test FallbackLLMClient fallback to next client on error
    c1_fail = DummyClient("primary_fail", should_fail=True)
    c2_ok = DummyClient("fallback_ok", should_fail=False, response="c2_response")
    fallback_client_fail = FallbackLLMClient(c1_fail, [c2_ok])
    
    res = await fallback_client_fail.generate("hello")
    assert res == "c2_response", f"Expected fallback response, got {res}"
    assert c1_fail.generate_calls == 1, "Primary client should have been called and failed"
    assert c2_ok.generate_calls == 1, "Fallback client should have been called"
    print("[OK] FallbackLLMClient recovery passed")

    # 4. Test FallbackLLMClient raises when all fail
    c1_fail2 = DummyClient("primary_fail2", should_fail=True)
    c2_fail2 = DummyClient("fallback_fail2", should_fail=True)
    fallback_all_fail = FallbackLLMClient(c1_fail2, [c2_fail2])
    
    try:
        await fallback_all_fail.generate("hello")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "All configured LLM clients failed" in str(e)
    print("[OK] FallbackLLMClient all-fail handling passed")

    print("\nALL LLM INTEGRATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
