# 10Figure Benchmark

End-to-end benchmark for evaluating coding agents on large-scale codebases using the 10Figure corpus (Kubernetes, Envoy, Django, TensorFlow).

## Prerequisites

- **Docker or Podman** installed and running
- **Python 3.8+** with `pyyaml` and `jinja2` (`pip install pyyaml jinja2`)
- **~10GB disk space** (~5GB corpus + ~6-8GB Docker image)

## Setup

### Step 1: Clone and build the 10Figure-Codebases corpus

```bash
git clone https://github.com/<org>/10Figure-Codebases.git ~/10Figure-Codebases
cd ~/10Figure-Codebases
make install
make build-corpus   # Downloads and prepares source repos
```

This produces `~/10Figure-Codebases/src/` with subdirectories for each project (kubernetes, envoy, django, tensorflow).

### Step 2: Build the base Docker image

The base image embeds the entire corpus so individual tasks don't need to re-copy it.

```bash
cd benchmarks/10figure/base

# Uses ~/10Figure-Codebases by default
./build.sh

# Or specify a custom corpus location
CORPUS_PATH=/path/to/10Figure-Codebases ./build.sh
```

Verify the image:

```bash
docker run --rm harbor-10figure:base ls /10figure/src
# Expected output: django  envoy  kubernetes  tensorflow
```

See `base/README.md` for details on the image contents and build process.

### Step 3: Run tasks with Harbor

Each task directory contains everything Harbor needs:

```bash
harbor run \
  --dockerfile benchmarks/10figure/<task_id>/environment/Dockerfile \
  --test-script benchmarks/10figure/<task_id>/tests/test.sh \
  --config benchmarks/10figure/<task_id>/task.toml
```

To verify the pipeline works, run the smoke-test task first:

```bash
harbor run \
  --dockerfile benchmarks/10figure/simple_test_01/environment/Dockerfile \
  --test-script benchmarks/10figure/simple_test_01/tests/test.sh
```

## Directory Structure

```
benchmarks/10figure/
├── README.md                    # This file
├── base/
│   ├── Dockerfile               # Base image with corpus
│   ├── build.sh                 # Build script for base image
│   └── README.md                # Base image documentation
├── scripts/
│   └── gen_harbor_tasks.py      # Task generator from 10Figure YAMLs
├── templates/
│   └── test.sh.j2               # Jinja2 template for test scripts
├── simple_test_01/              # Smoke-test task (pipeline verification)
│   ├── instruction.md
│   ├── environment/Dockerfile
│   └── tests/test.sh
├── api_upgrade_01/              # API migration task
├── bug_localization_01/         # Bug finding task
├── cross_file_reasoning_01/     # Cross-file tracing task
└── refactor_rename_01/          # Symbol rename task
```

Each task directory follows this structure:

```
<task_id>/
├── instruction.md               # Human-readable task description
├── task.toml                    # Harbor task metadata
├── task.yaml                    # 10Figure task definition (for validator)
├── environment/
│   └── Dockerfile               # Task-specific container (inherits base)
└── tests/
    ├── test.sh                  # Validation script
    └── expected_changes.json    # Ground truth for scoring
```

## Generating New Tasks

To generate Harbor tasks from 10Figure YAML definitions:

```bash
python3 benchmarks/10figure/scripts/gen_harbor_tasks.py \
  --input ~/10Figure-Codebases/tasks \
  --output benchmarks/10figure \
  --templates benchmarks/10figure/templates \
  --repo kubernetes \
  --corpus-root /10figure
```

### Parameters

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--input` | Yes | — | Directory containing 10Figure task YAML files |
| `--output` | Yes | — | Output directory for generated Harbor tasks |
| `--templates` | No | `templates` | Directory containing Jinja2 templates |
| `--repo` | No | `kubernetes` | Target repository name |
| `--corpus-root` | No | `/10figure` | Corpus root path inside the container |

## Task Types

| Type | Description |
|------|-------------|
| `cross_file_reasoning` | Trace function call chains across files |
| `refactor_rename` | Rename symbols throughout a codebase |
| `api_upgrade` | Migrate deprecated API patterns |
| `bug_localization` | Localize and fix bugs from error messages |

## Validation Pipeline

Each task's `tests/test.sh` script:

1. Checks for the agent's patch file at `/logs/agent/patch.diff`
2. Runs `validate_patch.py` with the patch and task definition
3. Extracts the overall score from the validation result
4. Writes the score to `/logs/verifier/reward.txt`

The validator expects:
- Patch file in unified diff format
- Task YAML with ground truth definition
- Access to corpus at `/10figure` with `scripts/validate_patch.py`
