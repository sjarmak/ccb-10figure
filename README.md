# 10Figure Synthetic Benchmark

Synthetic benchmark tasks generated from the 10Figure corpus, testing code understanding and modification on the Kubernetes codebase.

Part of [CodeContextBench](https://github.com/sjarmak/CodeContextBench).

## Overview

| Attribute | Value |
|-----------|-------|
| **Tasks** | 4 |
| **Source Repository** | [kubernetes/kubernetes](https://github.com/kubernetes/kubernetes) |
| **Language** | Go |
| **Task Types** | API upgrade, bug localization, cross-file reasoning, refactoring |
| **Difficulty** | Hard |
| **Evaluation** | Patch validation against expected changes |

## What This Benchmark Tests

Each task type evaluates a different aspect of agent capability:

| Task ID | Type | Description |
|---------|------|-------------|
| `api_upgrade_01` | API Migration | Migrate from `pointer.Int32()` to generic `ptr.To[int32]()` across codebase |
| `bug_localization_01` | Bug Localization | Find nil pointer dereference in EventedPLEG status update |
| `cross_file_reasoning_01` | Cross-File Reasoning | Trace Pod creation request flow from HTTP handler to validation |
| `refactor_rename_01` | Rename/Refactoring | Rename symbols throughout codebase |

## Task Structure

```
api_upgrade_01/
├── task.toml           # Harbor task metadata
├── instruction.md      # Task description with search hints
├── task.yaml           # 10Figure task definition (for validator)
├── repo_path           # Path to repository in container
├── environment/
│   └── Dockerfile      # Container with Kubernetes codebase at /10figure/src/kubernetes
└── tests/
    ├── test.sh         # Validation script (generated from template)
    └── expected_changes.json  # Expected patch content
```

## How Tasks Are Generated

Tasks are generated from 10Figure YAML definitions using a Jinja2 template:

```bash
python3 runners/gen_harbor_tasks.py \
  --input <path/to/10figure/tasks> \
  --output benchmarks/10figure \
  --templates benchmarks/10figure/templates \
  --repo kubernetes \
  --corpus-root /10figure
```

The `templates/test.sh.j2` template generates validation scripts that:
1. Check for agent patch file at `/logs/agent/patch.diff`
2. Run the validator with the patch and task definition
3. Extract the overall score
4. Write the score to `/logs/verifier/reward.txt`

## Running Tasks

```bash
harbor run \
  --path ccb-10figure/api_upgrade_01 \
  --agent-import-path agents.claude_baseline_agent:BaselineClaudeCodeAgent \
  --model anthropic/claude-haiku-4-5-20251001

# With MCP
source .env.local
export ANTHROPIC_API_KEY SOURCEGRAPH_ACCESS_TOKEN SOURCEGRAPH_URL

harbor run \
  --path ccb-10figure/api_upgrade_01 \
  --agent-import-path agents.mcp_variants:StrategicDeepSearchAgent \
  --model anthropic/claude-haiku-4-5-20251001
```

## Validation

The validator expects:
- Patch file in unified diff format at `/logs/agent/patch.diff`
- Task YAML with ground truth definition
- Access to corpus at `/10figure` with `scripts/validate_patch.py`

## License

Task definitions are licensed under Apache-2.0. The Kubernetes codebase is licensed under Apache-2.0.
