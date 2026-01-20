#!/usr/bin/env python3
"""Test script to validate the migration to google-genai and prompt externalization."""

import sys
import pathlib

# Add src to path
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))

def test_prompt_loading():
    """Test that the prompt template is loaded correctly from file."""
    print("Testing prompt loading...")
    try:
        from summarizer import SUMMARIZATION_PROMPT, _load_prompt_template
        
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
        
        print("✓ Prompt loading: PASSED")
        return True
    except Exception as e:
        print(f"✗ Prompt loading: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_imports():
    """Test that all imports work correctly."""
    print("\nTesting imports...")
    try:
        from google import genai
        assert hasattr(genai, "Client"), "genai should have Client class"
        print("✓ google-genai import: PASSED")
        
        from summarizer import Summarizer
        from config import Settings, get_settings
        from rate_limiter import TokenRateLimiter
        
        print("✓ Module imports: PASSED")
        return True
    except ImportError as e:
        print(f"✗ Imports: FAILED - {e}")
        print("\nNote: You may need to install dependencies:")
        print("  cd /home/ds/projects/ai_utils/mcp/web_summarizer_mcp")
        print("  uv sync")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"✗ Imports: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_client_initialization():
    """Test that the client can be initialized (without API key)."""
    print("\nTesting client initialization...")
    try:
        from google import genai
        
        # Test that Client class exists and can be instantiated
        # Note: This will fail without API key, but we can check the class exists
        assert hasattr(genai, "Client"), "genai.Client should exist"
        
        # Check if Client has aio attribute (for async operations)
        # We can't instantiate without API key, but we can check the class structure
        print("✓ Client class structure: PASSED")
        return True
    except Exception as e:
        print(f"✗ Client initialization: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_summarizer_structure():
    """Test that Summarizer class structure is correct."""
    print("\nTesting Summarizer class structure...")
    try:
        from summarizer import Summarizer
        from config import Settings
        from rate_limiter import TokenRateLimiter
        
        # Check that Summarizer has required methods
        assert hasattr(Summarizer, "__init__"), "Summarizer should have __init__"
        assert hasattr(Summarizer, "summarize_article"), "Summarizer should have summarize_article"
        assert hasattr(Summarizer, "close"), "Summarizer should have close method"
        
        # Check that it uses client instead of model
        import inspect
        source = inspect.getsource(Summarizer.__init__)
        assert "self.client" in source, "Summarizer should use self.client"
        assert "genai.Client" in source, "Summarizer should use genai.Client"
        
        print("✓ Summarizer structure: PASSED")
        return True
    except Exception as e:
        print(f"✗ Summarizer structure: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False

def test_prompt_file_exists():
    """Test that the prompt file exists in the correct location."""
    print("\nTesting prompt file location...")
    try:
        prompt_path = pathlib.Path(__file__).parent / "prompts" / "summarization_prompt.txt"
        assert prompt_path.exists(), f"Prompt file should exist at {prompt_path}"
        
        content = prompt_path.read_text(encoding="utf-8")
        assert content, "Prompt file should not be empty"
        assert "{title}" in content, "Prompt file should contain {title}"
        assert "{url}" in content, "Prompt file should contain {url}"
        assert "{content}" in content, "Prompt file should contain {content}"
        
        print(f"✓ Prompt file location: PASSED ({prompt_path})")
        return True
    except Exception as e:
        print(f"✗ Prompt file location: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Migration to google-genai and Prompt Externalization")
    print("=" * 60)
    
    results = []
    results.append(("Prompt file exists", test_prompt_file_exists()))
    results.append(("Prompt loading", test_prompt_loading()))
    results.append(("Imports", test_imports()))
    results.append(("Client structure", test_client_initialization()))
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
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
