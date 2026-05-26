#!/usr/bin/env python3
"""Integration test for the migration."""

import sys
import pathlib

# Add src to path as a package
src_path = pathlib.Path(__file__).parent / "src"
sys.path.insert(0, str(src_path.parent))

def test_openai_import():
    """Test openai import."""
    print("Testing openai import...")
    try:
        import openai
        assert hasattr(openai, "AsyncOpenAI"), "openai should have AsyncOpenAI class"
        print("  ✓ openai imported successfully")
        print(f"  ✓ AsyncOpenAI class exists: {hasattr(openai, 'AsyncOpenAI')}")
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
        
        assert "openai.AsyncOpenAI" in init_source, "Should use openai.AsyncOpenAI"
        assert "self.client" in init_source, "Should use self.client"
        assert "client.chat.completions.create" in summarize_source or "self.client.chat.completions.create" in summarize_source, "Should use chat.completions.create"
        
        print("  ✓ All required methods present")
        print("  ✓ Uses openai.AsyncOpenAI")
        print("  ✓ Uses client.chat.completions.create for async")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Integration Tests - OpenRouter Migration Validation")
    print("=" * 60)
    
    results = []
    results.append(("openai import", test_openai_import()))
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
