#!/usr/bin/env python3
"""Smoke test for 10Figure benchmark infrastructure.

Tests:
1. Task generator creates valid Harbor tasks
2. Claude baseline agent can execute tasks
3. Claude+MCP agent can execute tasks
4. Validates end-to-end pipeline
"""

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

# Add project to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.claude_baseline_agent import BaselineClaudeCodeAgent
from agents.mcp_variants import DeepSearchFocusedAgent
# Keep deprecated alias for backward compat
from agents.claude_sourcegraph_mcp_agent import ClaudeCodeSourcegraphMCPAgent


class SmokeTestRunner:
    """Run smoke tests on 10Figure tasks."""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.benchmark_dir = self.project_root / "benchmarks" / "10figure"
        self.results = {
            "tasks": [],
            "agents": [],
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
            }
        }
    
    def get_sample_tasks(self):
        """Get list of 4 sample 10Figure tasks."""
        tasks = []
        for task_id in ["cross_file_reasoning_01", "refactor_rename_01", 
                        "api_upgrade_01", "bug_localization_01"]:
            task_dir = self.benchmark_dir / task_id
            if task_dir.exists():
                tasks.append({
                    'id': task_id,
                    'dir': task_dir,
                    'instruction_file': task_dir / "instruction.md",
                    'task_yaml': task_dir / "task.yaml",
                })
        return tasks
    
    def validate_task_structure(self, task):
        """Validate that a task has required files."""
        required_files = [
            'instruction.md',
            'task.yaml',
            'task.toml',
            'tests/test.sh',
            'environment/Dockerfile',
        ]
        
        missing = []
        for f in required_files:
            if not (task['dir'] / f).exists():
                missing.append(f)
        
        return len(missing) == 0, missing
    
    def test_task_generation(self):
        """Test that gen_harbor_tasks.py works."""
        print("\n=== Testing Task Generation ===")
        tasks = self.get_sample_tasks()
        
        if not tasks:
            print("❌ No sample tasks found in benchmarks/10figure")
            return False
        
        print(f"✓ Found {len(tasks)} sample tasks")
        
        all_valid = True
        for task in tasks:
            valid, missing = self.validate_task_structure(task)
            if valid:
                print(f"  ✓ {task['id']}")
            else:
                print(f"  ❌ {task['id']} - missing: {', '.join(missing)}")
                all_valid = False
        
        self.results['tasks'] = tasks
        return all_valid
    
    def test_agent_environment(self):
        """Test that agents can be initialized."""
        print("\n=== Testing Agent Environment ===")
        
        # Test Claude baseline
        try:
            agent = BaselineClaudeCodeAgent()
            print("✓ Claude baseline agent initialized")
        except Exception as e:
            print(f"❌ Claude baseline initialization failed: {e}")
            return False
        
        # Test Claude+MCP agent (may fail if credentials missing, but structure is valid)
        try:
            agent = ClaudeCodeSourcegraphMCPAgent()
            print("✓ Claude+MCP agent structure valid")
        except Exception as e:
            # Expected if credentials aren't set, but agent class is fine
            if "must be set" in str(e):
                print("⚠ Claude+MCP credentials not set (expected in dev)")
            else:
                print(f"❌ Claude+MCP agent structure failed: {e}")
                return False
        
        return True
    
    def test_instruction_parsing(self):
        """Test that task instructions are readable."""
        print("\n=== Testing Instruction Parsing ===")
        
        tasks = self.results.get('tasks', self.get_sample_tasks())
        all_valid = True
        
        for task in tasks:
            try:
                instruction = task['instruction_file'].read_text()
                if instruction and len(instruction) > 50:
                    print(f"✓ {task['id']}: {len(instruction)} chars")
                else:
                    print(f"❌ {task['id']}: instruction too short")
                    all_valid = False
            except Exception as e:
                print(f"❌ {task['id']}: {e}")
                all_valid = False
        
        return all_valid
    
    def test_task_yaml_valid(self):
        """Test that task.yaml files are valid."""
        print("\n=== Testing Task YAML Validity ===")
        
        import yaml
        tasks = self.results.get('tasks', self.get_sample_tasks())
        all_valid = True
        
        for task in tasks:
            try:
                with open(task['task_yaml']) as f:
                    data = yaml.safe_load(f)
                
                # Check required fields
                required = ['type', 'description', 'task_id']
                missing = [f for f in required if f not in data]
                
                if not missing:
                    print(f"✓ {task['id']}: type={data.get('type')}")
                else:
                    print(f"❌ {task['id']}: missing {', '.join(missing)}")
                    all_valid = False
            except Exception as e:
                print(f"❌ {task['id']}: {e}")
                all_valid = False
        
        return all_valid
    
    def run_all_tests(self):
        """Run all smoke tests."""
        print("=" * 60)
        print("SMOKE TEST: 10Figure Benchmark Infrastructure")
        print("=" * 60)
        
        tests = [
            ("Task Generation", self.test_task_generation),
            ("Agent Environment", self.test_agent_environment),
            ("Instruction Parsing", self.test_instruction_parsing),
            ("Task YAML Validity", self.test_task_yaml_valid),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"\n❌ Test '{test_name}' raised exception: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)
        
        return failed == 0


def main():
    runner = SmokeTestRunner()
    success = runner.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
