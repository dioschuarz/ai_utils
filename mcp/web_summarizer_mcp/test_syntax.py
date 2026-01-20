#!/usr/bin/env python3
"""Test script to validate syntax and structure without requiring dependencies."""

import ast
import pathlib
import sys

def test_python_syntax():
    """Test that all Python files have valid syntax."""
    print("Testing Python syntax...")
    src_dir = pathlib.Path(__file__).parent / "src"
    
    errors = []
    for py_file in src_dir.glob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source, filename=str(py_file))
            print(f"  ✓ {py_file.name}")
        except SyntaxError as e:
            errors.append(f"  ✗ {py_file.name}: {e}")
            print(f"  ✗ {py_file.name}: {e}")
    
    if errors:
        print(f"\n✗ Syntax check: FAILED ({len(errors)} errors)")
        return False
    else:
        print("✓ Syntax check: PASSED")
        return True

def test_prompt_file():
    """Test that prompt file exists and has correct format."""
    print("\nTesting prompt file...")
    prompt_path = pathlib.Path(__file__).parent / "prompts" / "summarization_prompt.txt"
    
    try:
        if not prompt_path.exists():
            print(f"  ✗ Prompt file not found: {prompt_path}")
            return False
        
        content = prompt_path.read_text(encoding="utf-8")
        
        checks = [
            ("not empty", bool(content)),
            ("contains {title}", "{title}" in content),
            ("contains {url}", "{url}" in content),
            ("contains {content}", "{content}" in content),
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                print(f"  ✓ {check_name}")
            else:
                print(f"  ✗ {check_name}")
                all_passed = False
        
        if all_passed:
            print("✓ Prompt file: PASSED")
            return True
        else:
            print("✗ Prompt file: FAILED")
            return False
            
    except Exception as e:
        print(f"  ✗ Error reading prompt file: {e}")
        return False

def test_imports_in_code():
    """Test that imports in code are correct (without executing)."""
    print("\nTesting import statements in code...")
    summarizer_file = pathlib.Path(__file__).parent / "src" / "summarizer.py"
    
    try:
        with open(summarizer_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        checks = [
            ("uses 'from google import genai'", "from google import genai" in content),
            ("does NOT use 'import google.generativeai'", "import google.generativeai" not in content),
            ("does NOT use 'google.generativeai'", "google.generativeai" not in content),
            ("uses pathlib", "import pathlib" in content),
            ("has _load_prompt_template function", "def _load_prompt_template" in content),
            ("uses genai.Client", "genai.Client" in content),
            ("uses client.aio", "client.aio" in content or "self.client.aio" in content),
            ("does NOT use asyncio.to_thread for generate_content", 
             "asyncio.to_thread" not in content or 
             ("asyncio.to_thread" in content and "generate_content" not in content.split("asyncio.to_thread")[1][:200])),
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                print(f"  ✓ {check_name}")
            else:
                print(f"  ✗ {check_name}")
                all_passed = False
        
        if all_passed:
            print("✓ Import checks: PASSED")
            return True
        else:
            print("✗ Import checks: FAILED")
            return False
            
    except Exception as e:
        print(f"  ✗ Error checking imports: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pyproject_toml():
    """Test that pyproject.toml has correct dependencies."""
    print("\nTesting pyproject.toml...")
    pyproject_file = pathlib.Path(__file__).parent / "pyproject.toml"
    
    try:
        content = pyproject_file.read_text(encoding="utf-8")
        
        checks = [
            ("has google-genai", "google-genai" in content),
            ("does NOT have google-generativeai", "google-generativeai" not in content),
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                print(f"  ✓ {check_name}")
            else:
                print(f"  ✗ {check_name}")
                all_passed = False
        
        if all_passed:
            print("✓ pyproject.toml: PASSED")
            return True
        else:
            print("✗ pyproject.toml: FAILED")
            return False
            
    except Exception as e:
        print(f"  ✗ Error reading pyproject.toml: {e}")
        return False

def test_dockerfile():
    """Test that Dockerfile includes prompts folder."""
    print("\nTesting Dockerfile...")
    dockerfile = pathlib.Path(__file__).parent / "Dockerfile"
    
    try:
        content = dockerfile.read_text(encoding="utf-8")
        
        if "COPY prompts" in content or "COPY prompts/" in content:
            print("  ✓ Dockerfile copies prompts folder")
            print("✓ Dockerfile: PASSED")
            return True
        else:
            print("  ✗ Dockerfile does not copy prompts folder")
            print("✗ Dockerfile: FAILED")
            return False
            
    except Exception as e:
        print(f"  ✗ Error reading Dockerfile: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Migration (Syntax & Structure Checks)")
    print("=" * 60)
    
    results = []
    results.append(("Python syntax", test_python_syntax()))
    results.append(("Prompt file", test_prompt_file()))
    results.append(("Code imports", test_imports_in_code()))
    results.append(("pyproject.toml", test_pyproject_toml()))
    results.append(("Dockerfile", test_dockerfile()))
    
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
        print("\n✓ All structural tests passed!")
        print("\nNote: To test with actual API calls, install dependencies:")
        print("  cd /home/ds/projects/ai_utils/mcp/web_summarizer_mcp")
        print("  uv sync")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
