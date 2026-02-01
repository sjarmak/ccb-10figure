#!/usr/bin/env python3
"""Validate benchmark setup before executing Harbor jobs.

Checks:
- Agent implementations load correctly
- Environment variables set
- Task directories exist and are valid
- Harbor/container runtime available
- Sufficient disk space
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class BenchmarkValidator:
    """Validate benchmark execution readiness."""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.errors = []
        self.warnings = []
        self.checks_passed = 0
        self.checks_total = 0
    
    def check(self, name: str, fn, critical=True) -> bool:
        """Run a validation check.
        
        Args:
            name: Check description
            fn: Callable that returns (bool, str) — (passed, message)
            critical: If True, failure aborts execution
            
        Returns:
            True if check passed
        """
        self.checks_total += 1
        
        try:
            passed, message = fn()
            
            if passed:
                self.checks_passed += 1
                print(f"  ✓ {name}")
                if message:
                    print(f"    {message}")
                return True
            else:
                if critical:
                    self.errors.append(f"{name}: {message}")
                else:
                    self.warnings.append(f"{name}: {message}")
                print(f"  ✗ {name}")
                if message:
                    print(f"    {message}")
                return False
        except Exception as e:
            if critical:
                self.errors.append(f"{name}: {str(e)}")
            else:
                self.warnings.append(f"{name}: {str(e)}")
            print(f"  ✗ {name}: {str(e)}")
            return False
    
    # ========================================================================
    # Validation Checks
    # ========================================================================
    
    def validate_agents(self) -> bool:
        """Check agent implementations load correctly."""
        print("\n[AGENTS]")
        
        try:
            from agents.claude_baseline_agent import BaselineClaudeCodeAgent
            baseline = BaselineClaudeCodeAgent()
            self.check(
                "BaselineClaudeCodeAgent (baseline) loads",
                lambda: (
                    baseline._install_agent_template_path.exists(),
                    f"Template: {baseline._install_agent_template_path}"
                ),
                critical=True
            )
        except Exception as e:
            self.errors.append(f"BaselineClaudeCodeAgent load failed: {str(e)}")
            print(f"  ✗ BaselineClaudeCodeAgent (baseline) loads: {str(e)}")
            return False
        
        try:
            from agents.mcp_variants import DeepSearchFocusedAgent
            mcp = DeepSearchFocusedAgent()
            self.check(
                "ClaudeCodeSourcegraphMCPAgent (MCP) loads",
                lambda: (
                    mcp._install_agent_template_path.exists(),
                    f"Template: {mcp._install_agent_template_path}"
                ),
                critical=True
            )
        except Exception as e:
            self.errors.append(f"ClaudeCodeSourcegraphMCPAgent load failed: {str(e)}")
            print(f"  ✗ ClaudeCodeSourcegraphMCPAgent (MCP) loads: {str(e)}")
            return False
        
        return True
    
    def validate_environment(self) -> bool:
        """Check required environment variables."""
        print("\n[ENVIRONMENT]")
        
        # Check ANTHROPIC_API_KEY
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.check(
            "ANTHROPIC_API_KEY set",
            lambda: (
                bool(api_key),
                f"Key: {api_key[:20]}..." if api_key else "Not set"
            ),
            critical=True
        )
        
        # Check SRC_ACCESS_TOKEN
        src_token = os.environ.get("SRC_ACCESS_TOKEN")
        self.check(
            "SRC_ACCESS_TOKEN set",
            lambda: (
                bool(src_token),
                f"Token: {src_token[:20]}..." if src_token else "Not set (needed for --agent claude-mcp)"
            ),
            critical=False  # Non-critical for baseline
        )
        
        # Check SOURCEGRAPH_URL (optional, has default)
        sg_url = os.environ.get("SOURCEGRAPH_URL", "https://sourcegraph.sourcegraph.com")
        self.check(
            "SOURCEGRAPH_URL configured",
            lambda: (True, f"URL: {sg_url}"),
            critical=False
        )
        
        return True
    
    def validate_tasks(self) -> bool:
        """Check task directories exist and are valid."""
        print("\n[TASKS]")
        
        # Check github_mined tasks exist
        github_mined = self.project_root / "benchmarks" / "github_mined"
        self.check(
            "benchmarks/github_mined/ exists",
            lambda: (
                github_mined.exists() and github_mined.is_dir(),
                f"Path: {github_mined}"
            ),
            critical=True
        )
        
        if github_mined.exists():
            task_dirs = list(github_mined.glob("sgt-*"))
            self.check(
                "Tasks exist in github_mined/",
                lambda: (
                    len(task_dirs) > 0,
                    f"Found {len(task_dirs)} tasks (sgt-001 through sgt-{len(task_dirs):03d})"
                ),
                critical=True
            )
            
            # Spot-check first task
            if task_dirs:
                first_task = sorted(task_dirs)[0]
                required_files = [
                    "instruction.md",
                    "task.toml",
                    "environment/Dockerfile",
                    "tests/test.sh",
                    "repo_path"
                ]
                
                missing = []
                for fname in required_files:
                    if not (first_task / fname).exists():
                        missing.append(fname)
                
                self.check(
                    f"First task ({first_task.name}) has required files",
                    lambda: (
                        len(missing) == 0,
                        f"Files: {', '.join(required_files)} — " + 
                        (f"Missing: {', '.join(missing)}" if missing else "All present")
                    ),
                    critical=True
                )
        
        # Check 10figure tasks (optional, may not be set up yet)
        ten_figure = self.project_root / "benchmarks" / "10figure"
        if ten_figure.exists():
            task_dirs = list(ten_figure.glob("*"))
            self.check(
                "10figure tasks exist (optional)",
                lambda: (True, f"Found {len(task_dirs)} tasks"),
                critical=False
            )
        
        return True
    
    def validate_infrastructure(self) -> bool:
        """Check Harbor/container infrastructure."""
        print("\n[INFRASTRUCTURE]")
        
        # Check container runtime
        container_runtime = os.environ.get("CONTAINER_RUNTIME", "podman")
        self.check(
            f"{container_runtime} available",
            lambda: self._check_command(container_runtime, "--version"),
            critical=True
        )
        
        # Check Harbor CLI (optional, may use Python wrapper)
        try:
            result = subprocess.run(
                ["harbor", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            has_harbor = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            has_harbor = False
        
        self.check(
            "Harbor CLI available",
            lambda: (
                has_harbor,
                "Harbor CLI found in PATH (optional if using Python runner)"
            ),
            critical=False
        )
        
        # Check Docker/Podman wrapper
        docker_wrapper = Path(os.path.expanduser("~/.local/bin/docker"))
        self.check(
            "Docker wrapper script",
            lambda: (
                docker_wrapper.exists() or container_runtime == "docker",
                f"Path: {docker_wrapper} (needed for podman compatibility)" if container_runtime == "podman" else "Using docker directly"
            ),
            critical=False
        )
        
        return True
    
    def validate_disk_space(self) -> bool:
        """Check available disk space."""
        print("\n[DISK SPACE]")
        
        # Check jobs directory
        jobs_dir = self.project_root / "jobs"
        jobs_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            import shutil
            stat = shutil.disk_usage(str(jobs_dir))
            available_gb = stat.free / (1024**3)
            
            self.check(
                "Sufficient disk space for jobs/",
                lambda: (
                    available_gb > 5,
                    f"Available: {available_gb:.1f} GB (recommend: >10 GB)"
                ),
                critical=False
            )
        except Exception as e:
            self.warnings.append(f"Could not check disk space: {str(e)}")
        
        return True
    
    def validate_config_files(self) -> bool:
        """Check configuration files."""
        print("\n[CONFIGURATION]")
        
        # Check harbor-config.yaml
        harbor_config = self.project_root / "infrastructure" / "harbor-config.yaml"
        self.check(
            "infrastructure/harbor-config.yaml exists",
            lambda: (
                harbor_config.exists(),
                f"Path: {harbor_config}"
            ),
            critical=True
        )
        
        # Check datasets.yaml
        datasets_config = self.project_root / "infrastructure" / "datasets.yaml"
        self.check(
            "infrastructure/datasets.yaml exists",
            lambda: (
                datasets_config.exists(),
                f"Path: {datasets_config}"
            ),
            critical=True
        )
        
        # Check .env.local
        env_local = self.project_root / ".env.local"
        self.check(
            ".env.local exists",
            lambda: (
                env_local.exists(),
                f"Path: {env_local} (has credentials)"
            ),
            critical=False
        )
        
        return True
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _check_command(self, cmd: str, *args) -> Tuple[bool, str]:
        """Check if a command exists and runs successfully."""
        try:
            result = subprocess.run(
                [cmd, *args],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Extract version if available
                version = result.stdout.split('\n')[0] if result.stdout else ""
                return True, version if version else "Available"
            else:
                return False, result.stderr or "Command failed"
        except FileNotFoundError:
            return False, f"{cmd} not found in PATH"
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    # ========================================================================
    # Main Validation Flow
    # ========================================================================
    
    def run_all_checks(self) -> bool:
        """Run all validation checks.
        
        Returns:
            True if all critical checks passed
        """
        print("=" * 70)
        print("BENCHMARK SETUP VALIDATION (Phase 2b: CodeContextBench-cy6)")
        print("=" * 70)
        
        self.validate_agents()
        self.validate_environment()
        self.validate_tasks()
        self.validate_infrastructure()
        self.validate_disk_space()
        self.validate_config_files()
        
        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Checks passed: {self.checks_passed}/{self.checks_total}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if not self.errors:
            print("\n✅ ALL CRITICAL CHECKS PASSED")
            print("\nReady to execute benchmarks:")
            print("  ./runners/harbor_benchmark.sh --benchmark github_mined --agent claude-baseline --tasks 10 --concurrent 2")
            print("  ./runners/harbor_benchmark.sh --benchmark github_mined --agent claude-mcp --tasks 10 --concurrent 2")
            return True
        else:
            print("\n❌ CRITICAL CHECKS FAILED")
            print("\nFix errors above before running benchmarks.")
            return False


def main():
    """CLI entry point."""
    validator = BenchmarkValidator()
    success = validator.run_all_checks()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
