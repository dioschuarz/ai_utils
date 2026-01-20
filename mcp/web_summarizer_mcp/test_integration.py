#!/usr/bin/env python3
"""Integration test for the migration."""

import sys
import pathlib

# Add src to path as a package
src_path = pathlib.Path(__file__).parent / "src"
sys.path.insert(0, str(src_path.parent))

def test_google_genai_import():
    """Test google-genai import."""
    print("Testing google-genai import...")
    try:
        from google import genai
        assert hasattr(genai, "Client"), "genai should have Client class"
        print("  ✓ google-genai imported successfully")
        print(f"  ✓ Client class exists: {hasattr(genai, 'Client')}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def test_prompt_loading():
    """Test prompt loading from file."""
    print("\nTesting prompt loading...")
    try:
        from src.summarizer import SUMMARIZATION_PROMPT, _load_prompt_template
        
        # Test direct function call
        prompt = _load_prompt_template()
        assert prompt, "Prompt should not be empty"
        assert "{title}" in prompt, "Prompt should contain {title} placeholder"
        assert "{url}" in prompt, "Prompt should contain {url} placeholder"
        assert "{content}" in prompt, "Prompt should contain {content} placeholder"
        
        # Test module-level constant
        assert SUMMARIZATION_PROMPT == prompt, "Module constant should match loaded prompt"
        
        # Test formatting
        formatted = SUMMARIZATION_PROMPT.format(
            title="Test Title",
            url="https://example.com",
            content="Test content"
        )
        assert "Test Title" in formatted, "Formatted prompt should contain title"
        assert "https://example.com" in formatted, "Formatted prompt should contain URL"
        assert "Test content" in formatted, "Formatted prompt should contain content"
        
        print(f"  ✓ Prompt loaded: {len(SUMMARIZATION_PROMPT)} chars")
        print("  ✓ All placeholders present")
        print("  ✓ Formatting works correctly")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_summarizer_structure():
    """Test Summarizer class structure."""
    print("\nTesting Summarizer class structure...")
    try:
        from src.summarizer import Summarizer
        import inspect
        
        # Check methods
        assert hasattr(Summarizer, "__init__"), "Summarizer should have __init__"
        assert hasattr(Summarizer, "summarize_article"), "Summarizer should have summarize_article"
        assert hasattr(Summarizer, "close"), "Summarizer should have close method"
        
        # Check implementation
        init_source = inspect.getsource(Summarizer.__init__)
        summarize_source = inspect.getsource(Summarizer.summarize_article)
        
        assert "genai.Client" in init_source, "Should use genai.Client"
        assert "self.client" in init_source, "Should use self.client"
        assert "client.aio" in summarize_source or "self.client.aio" in summarize_source, "Should use client.aio"
        assert "asyncio.to_thread" not in summarize_source or "generate_content" not in summarize_source.split("asyncio.to_thread")[1][:300], "Should NOT use asyncio.to_thread for generate_content"
        
        print("  ✓ All required methods present")
        print("  ✓ Uses genai.Client")
        print("  ✓ Uses client.aio for async")
        print("  ✓ No deprecated asyncio.to_thread for generate_content")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Integration Tests - Migration Validation")
    print("=" * 60)
    
    results = []
    results.append(("google-genai import", test_google_genai_import()))
    results.append(("Prompt loading", test_prompt_loading()))
    results.append(("Summarizer structure", test_summarizer_structure()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All integration tests passed!")
        print("\nMigration validation: SUCCESS")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
