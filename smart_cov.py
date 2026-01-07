from pathlib import Path
import sys

# Smart Coverage Logic
def pytest_load_initial_conftests(early_config, parser, args):
    """
    Dynamically inject coverage arguments based on the test target.

    Heuristic:
    1. If specific test files are provided (e.g., `tests/unit/test_cli.py`),
       calculate coverage ONLY for the corresponding source file (`src/cyberred/cli.py`).
    2. If no specific files are provided (full suite run),
       default to global coverage (`--cov=src`).
    """
    # Check if we are already passing coverage args (avoid double injection)
    if any("--cov" in arg for arg in args):
        return

    test_files = [arg for arg in args if arg.endswith(".py") and "test" in arg]

    coverage_sources = []
    
    if test_files:
        # Targeted Run: Map tests to source files
        for test_file in test_files:
            # Simple heuristic: tests/unit/test_foo.py -> src/cyberred/foo.py
            path = Path(test_file)
            parts = path.parts
            
            try:
                # Find where 'tests' starts
                idx = 0
                if 'tests' in parts:
                    idx = parts.index('tests') + 1 
                
                # Suffix after tests/
                suffix = list(parts[idx:])
                
                # Remove typical test types
                if suffix and suffix[0] in ['unit', 'integration', 'safety', 'emergence', 'e2e', 'chaos', 'load']:
                    suffix.pop(0)
                    
                # Now we have ('daemon', 'test_server.py')
                if suffix:
                    filename = suffix[-1]
                    if filename.startswith("test_"):
                        # 'test_server.py' -> 'server.py'
                        source_name = filename[5:]
                        suffix[-1] = source_name
                        
                        # Reconstruct source path
                        # src/cyberred/daemon/server.py
                        source_path = Path("src/cyberred").joinpath(*suffix)
                        
                        if source_path.exists():
                            coverage_sources.append(str(source_path))
            except Exception:
                pass 

    # Inject arguments
    if coverage_sources:
        print(f"Smart Coverage: Targeting {len(coverage_sources)} file(s)")
        for src in coverage_sources:
            args.append(f"--cov={src}")
    else:
        # Global fallback
        if not any(arg in ["-h", "--help", "--collect-only"] for arg in args):
             print("Smart Coverage: Global Fallback (Full Suite)")
             args.append("--cov=src")

    # Always enforce strict 100% and formatting
    args.append("--cov-report=term-missing:skip-covered")
    args.append("--cov-report=xml:coverage.xml")
    args.append("--cov-fail-under=100")
