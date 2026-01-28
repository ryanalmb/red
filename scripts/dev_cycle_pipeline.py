#!/usr/bin/env python3
"""BMAD → RovoDev Pipeline CLI

Runs one or more BMAD stories in sequence (or an entire epic) by spawning a fresh
`acli rovodev run --yolo` process per stage.

Stages per story:
  1) Create Story (optional)
  2) Dev Story
  3) Code Review (retry up to N)

State/resume:
  - Saves progress to `.rovodev/pipeline/state.json`
  - Outputs per stage to `.rovodev/pipeline/runs/<story_key>/<stage>-output.txt`

Global requirements injected into every stage:
  - STRICT TDD
  - Activate `venv` (not `.venv`)
  - 100% coverage (targeted subset only; never run full suite)
  - Integration tests: real production code, minimal mocking
  - Always load full files and full epic context

Usage examples:
  # Run a single story
  ./bmad-pipeline --epic 7 --stories 21

  # Run multiple stories in epic 7
  ./bmad-pipeline --epic 7 --stories 19,20,21

  # Run a range of stories in epic 7
  ./bmad-pipeline --epic 7 --stories 19-23

  # Run an entire epic (discover all stories in epic)
  ./bmad-pipeline --epic 7 --whole-epic

  # Resume after interruption
  ./bmad-pipeline --resume

"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple


# =============================================================================
# GLOBAL RULES - Applied to ALL stage task descriptions
# =============================================================================

GLOBAL_RULES = """
## MANDATORY RULES FOR THIS TASK

### Environment
- ALWAYS activate virtual environment first: `source venv/bin/activate`
- Run all Python/pytest commands INSIDE the activated venv

### Test-Driven Development (TDD)
- STRICT TDD: Write tests FIRST, then implementation - NO EXCEPTIONS
- Red-Green-Refactor cycle:
  1. Write a failing test (RED)
  2. Write minimal code to pass (GREEN)
  3. Refactor while keeping tests green

### Coverage Policy (CRITICAL)
- 100% test coverage is MANDATORY.
- BUT: At NO point should the FULL test suite be run.
- Run ONLY targeted tests relevant to the change (single file, single test, or small subset).
- Coverage checks MUST also be targeted (scope-limited), e.g.:
  - `pytest tests/unit/path/to/test_file.py --cov=src --cov-report=term-missing --cov-fail-under=100`
  - `pytest tests/integration/path/to/test_file.py --cov=src --cov-report=term-missing --cov-fail-under=100`
- Avoid: `pytest` (no path) or running all of `tests/`.

### Integration Tests (MANDATORY)
- Write STRICT integration tests that test ACTUAL PRODUCTION CODE
- NO MOCKS or MINIMAL mocks only - test real behavior
- Place integration tests in `tests/integration/`
- Run ONLY the relevant integration tests you add/modify

### File Reading
- When reading workflow files, ALWAYS expand truncated content fully
- Do NOT work with partial/truncated file content

### Epic Context
- When creating/working on a story, load the ENTIRE epic context (all stories in that epic)
"""


# =============================================================================
# State models
# =============================================================================


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStatus(str, Enum):
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class StageResult:
    stage_id: str
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    retry_count: int = 0
    output_file: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class StoryRunState:
    epic: int
    story: int
    story_key: str
    story_file: Optional[str] = None
    current_stage_idx: int = 0
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class BatchState:
    pipeline_id: str
    status: PipelineStatus = PipelineStatus.NOT_STARTED
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    # Queue
    story_queue: List[Dict[str, Any]] = field(default_factory=list)  # [{epic, story, story_key, story_file?}]
    current_story_idx: int = 0

    # Current story run
    current_story: Optional[StoryRunState] = None

    STATE_FILE: Path = Path(".rovodev/pipeline/state.json")

    def save(self) -> None:
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.STATE_FILE, "w") as f:
            json.dump(self._to_dict(), f, indent=2)

    @classmethod
    def load(cls) -> Optional[BatchState]:
        if not cls.STATE_FILE.exists():
            return None
        data = json.loads(cls.STATE_FILE.read_text())
        st = cls(pipeline_id=data["pipeline_id"])
        st.status = PipelineStatus(data.get("status", PipelineStatus.NOT_STARTED.value))
        st.start_time = data.get("start_time")
        st.end_time = data.get("end_time")
        st.story_queue = data.get("story_queue", [])
        st.current_story_idx = data.get("current_story_idx", 0)
        cs = data.get("current_story")
        if cs:
            st.current_story = StoryRunState(
                epic=cs["epic"],
                story=cs["story"],
                story_key=cs["story_key"],
                story_file=cs.get("story_file"),
                current_stage_idx=cs.get("current_stage_idx", 0),
                stages=cs.get("stages", {}),
            )
        return st

    @classmethod
    def clear(cls) -> None:
        if cls.STATE_FILE.exists():
            cls.STATE_FILE.unlink()

    def _to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "story_queue": self.story_queue,
            "current_story_idx": self.current_story_idx,
            "current_story": asdict(self.current_story) if self.current_story else None,
        }


# =============================================================================
# Stage definitions
# =============================================================================

STAGES = [
    {"id": "create-story", "name": "Create Story", "gate": False, "workflow": ".rovodev/workflows/create-story.md", "skip_if_story_file": True},
    {"id": "dev-story", "name": "Dev Story", "gate": False, "workflow": ".rovodev/workflows/dev-story.md"},
    {"id": "code-review", "name": "Code Review", "gate": False, "workflow": ".rovodev/workflows/code-review.md", "max_retries": 2},
]


# =============================================================================
# Epic/story parsing
# =============================================================================

EPICS_FILE = Path("_bmad-output/planning-artifacts/epics-stories.md")


def discover_stories_in_epic(epic: int) -> List[int]:
    """Return sorted story numbers for an epic by parsing epics-stories.md headings.

    Expected format: '### Story 7.21: ...'
    """
    if not EPICS_FILE.exists():
        raise FileNotFoundError(f"Missing epics file: {EPICS_FILE}")
    content = EPICS_FILE.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"^###\s+Story\s+{epic}\.(\d+)\s*:", re.MULTILINE)
    nums = sorted({int(m.group(1)) for m in pattern.finditer(content)})
    return nums


def parse_story_selector(selector: str) -> List[int]:
    """Parse --stories argument.

    Supports:
      - '21'
      - '19,20,21'
      - '19-23'
      - '19-23,25,27'
    """
    out: List[int] = []
    for part in selector.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(list(range(int(a), int(b) + 1)))
        else:
            out.append(int(part))
    # stable unique
    seen = set()
    uniq = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


# =============================================================================
# Task generation
# =============================================================================

def stage_output_dir(story_key: str) -> Path:
    return Path(".rovodev/pipeline/runs") / story_key


def get_story_glob(epic: int, story: int) -> str:
    return f"_bmad-output/implementation-artifacts/{epic}-{story}-*.md"


def get_stage_task(stage_id: str, story: StoryRunState) -> str:
    epic = story.epic
    story_num = story.story
    story_key = story.story_key
    story_file = story.story_file or get_story_glob(epic, story_num)

    if stage_id == "create-story":
        return f"""
{GLOBAL_RULES}

## TASK: Create Story {story_key}

Create story {epic}.{story_num} from Epic {epic}.

1. Read and follow workflow: @.rovodev/workflows/create-story.md
2. Load FULL epic {epic} context from: @_bmad-output/planning-artifacts/epics-stories.md
3. Run autonomously (YOLO)
4. Create story file under: _bmad-output/implementation-artifacts/

Required output line:
STORY_FILE: _bmad-output/implementation-artifacts/{epic}-{story_num}-<name>.md
""".strip()

    if stage_id == "dev-story":
        return f"""
{GLOBAL_RULES}

## TASK: Implement Story {story_key}

Implement story using strict TDD and targeted 100% coverage checks.

Story file: @{story_file}

1. Read and follow workflow: @.rovodev/workflows/dev-story.md
2. Load full files:
   - Architecture: @_bmad-output/planning-artifacts/architecture.md
   - Full Epic {epic}: @_bmad-output/planning-artifacts/epics-stories.md
3. Run autonomously (YOLO)

Required output line:
DEV_STATUS: DONE or BLOCKED
""".strip()

    if stage_id == "code-review":
        return f"""
{GLOBAL_RULES}

## TASK: Adversarial Code Review {story_key}

Story file: @{story_file}

1. Read and follow workflow: @.rovodev/workflows/code-review.md
2. Be adversarial. Find 3-10 issues. Fix them.
3. Keep tests targeted (never full suite) and maintain 100% coverage.

Required output line:
REVIEW_STATUS: PASS or NEEDS_FIXES
""".strip()

    raise ValueError(f"Unknown stage: {stage_id}")


# =============================================================================
# Runner
# =============================================================================

class Pipeline:
    def __init__(
        self,
        epic: Optional[int],
        stories: Optional[List[int]],
        whole_epic: bool,
        resume: bool,
        story_file: Optional[str],
        max_retries: int,
    ):
        self.max_retries = max_retries

        if resume:
            loaded = BatchState.load()
            if not loaded:
                raise SystemExit("--resume specified but no saved state found")
            self.state = loaded
            return

        if story_file:
            # Treat as single story run; attempt to infer epic/story from filename
            inferred = infer_epic_story_from_path(story_file)
            if not inferred:
                raise SystemExit("Could not infer epic/story from --story-file. Provide --epic and --stories.")
            epic_i, story_i = inferred
            stories_list = [story_i]
            epic = epic_i
        else:
            if not epic:
                raise SystemExit("--epic is required (unless using --story-file or --resume)")
            if whole_epic:
                stories_list = discover_stories_in_epic(epic)
                if not stories_list:
                    raise SystemExit(f"No stories discovered for epic {epic}")
            else:
                if not stories:
                    raise SystemExit("Provide --stories (e.g. 21 or 19-23) or --whole-epic")
                stories_list = stories

        pipeline_id = f"pipeline-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.state = BatchState(pipeline_id=pipeline_id)
        self.state.status = PipelineStatus.NOT_STARTED
        self.state.story_queue = [
            {"epic": epic, "story": s, "story_key": f"{epic}-{s}", "story_file": story_file if (story_file and s == stories_list[0]) else None}
            for s in stories_list
        ]
        self.state.current_story_idx = 0
        self.state.save()

    def run(self) -> int:
        self.state.status = PipelineStatus.RUNNING
        self.state.start_time = datetime.now().isoformat()
        self.state.save()

        try:
            _loop_iteration = 0
            while self.state.current_story_idx < len(self.state.story_queue):
                _loop_iteration += 1
                print(f"[TRACE] Loop iteration {_loop_iteration}: current_story_idx={self.state.current_story_idx}, queue_len={len(self.state.story_queue)}")
                item = self.state.story_queue[self.state.current_story_idx]
                story_state = self._init_or_load_story(item)

                rc = self._run_single_story(story_state)
                print(f"[TRACE] _run_single_story({story_state.story_key}) returned rc={rc}")
                if rc != 0:
                    self.state.status = PipelineStatus.FAILED if rc != 130 else PipelineStatus.ABORTED
                    self.state.end_time = datetime.now().isoformat()
                    self.state.save()
                    return rc

                # Story success
                print(f"[TRACE] Story {story_state.story_key} succeeded. Incrementing current_story_idx: {self.state.current_story_idx} -> {self.state.current_story_idx + 1}")
                self.state.current_story_idx += 1
                self.state.current_story = None
                self.state.save()

            # Batch success
            self.state.status = PipelineStatus.SUCCESS
            self.state.end_time = datetime.now().isoformat()
            self.state.save()
            BatchState.clear()
            return 0

        except KeyboardInterrupt:
            self.state.status = PipelineStatus.ABORTED
            self.state.end_time = datetime.now().isoformat()
            self.state.save()
            return 130

    def _init_or_load_story(self, item: Dict[str, Any]) -> StoryRunState:
        # Resume within current story if available
        if self.state.current_story and self.state.current_story.story_key == item["story_key"]:
            return self.state.current_story

        story = StoryRunState(
            epic=item["epic"],
            story=item["story"],
            story_key=item["story_key"],
            story_file=item.get("story_file"),
            current_stage_idx=0,
            stages={}
        )
        for s in STAGES:
            story.stages[s["id"]] = asdict(StageResult(stage_id=s["id"], stage_name=s["name"]))
        self.state.current_story = story
        self.state.save()
        return story

    def _run_single_story(self, story: StoryRunState) -> int:
        print(f"\n=== Running story {story.story_key} (index {self.state.current_story_idx+1}/{len(self.state.story_queue)}) ===")
        print(f"[TRACE] _run_single_story started for {story.story_key}, current_stage_idx={story.current_stage_idx}")

        for idx, stage in enumerate(STAGES):
            # If resuming within a story
            if idx < story.current_stage_idx:
                continue

            if stage.get("skip_if_story_file") and story.story_file:
                # skip create-story if provided
                sr = story.stages[stage["id"]]
                sr["status"] = StageStatus.SKIPPED.value
                sr["error_message"] = "Story file provided"
                story.current_stage_idx = idx + 1
                self.state.current_story = story
                self.state.save()
                continue

            ok = self._run_stage(story, stage)
            if not ok:
                if stage.get("max_retries"):
                    retries = min(stage["max_retries"], self.max_retries)
                    for r in range(retries):
                        story.stages[stage["id"]]["retry_count"] = r + 1
                        ok = self._run_stage(story, stage)
                        if ok:
                            break

                if not ok:
                    # gate stops immediately
                    return 1

            story.current_stage_idx = idx + 1
            self.state.current_story = story
            self.state.save()

        print(f"[TRACE] _run_single_story completed all stages for {story.story_key}, returning 0")
        return 0

    def _run_stage(self, story: StoryRunState, stage: Dict[str, Any]) -> bool:
        stage_id = stage["id"]
        stage_name = stage["name"]
        sr = story.stages[stage_id]

        out_dir = stage_output_dir(story.story_key)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{stage_id}-output.txt"

        sr["status"] = StageStatus.RUNNING.value
        sr["start_time"] = datetime.now().isoformat()
        sr["output_file"] = str(output_file)
        self.state.current_story = story
        self.state.save()

        task = get_stage_task(stage_id, story)
        cmd = ["acli", "rovodev", "run", "--yolo", "--output-file", str(output_file), task]

        print(f"\n--- Stage: {stage_name} ({story.story_key}) ---")
        print(f"Output: {output_file}")

        try:
            res = subprocess.run(cmd, text=True, timeout=3600)
        except subprocess.TimeoutExpired:
            sr["status"] = StageStatus.FAILED.value
            sr["error_message"] = "Timeout"
            sr["end_time"] = datetime.now().isoformat()
            self.state.current_story = story
            self.state.save()
            return False

        sr["end_time"] = datetime.now().isoformat()
        sr["status"] = StageStatus.PASSED.value if res.returncode == 0 else StageStatus.FAILED.value
        if res.returncode != 0:
            sr["error_message"] = f"Exit code {res.returncode}"
            self.state.current_story = story
            self.state.save()
            return False

        # Post-process stage outputs
        if stage_id == "create-story":
            self._extract_story_file(story, output_file)

        return True

    def _extract_story_file(self, story: StoryRunState, output_file: Path) -> None:
        txt = output_file.read_text(encoding="utf-8", errors="replace") if output_file.exists() else ""
        # Match STORY_FILE with optional markdown bold markers (**)
        m = re.search(r"^\*{0,2}STORY_FILE:\s*(.+?)\*{0,2}$", txt, re.MULTILINE)
        if m:
            story.story_file = m.group(1).strip()
            # persist into queue item too
            self.state.story_queue[self.state.current_story_idx]["story_file"] = story.story_file
            self.state.current_story = story
            self.state.save()


def infer_epic_story_from_path(p: str) -> Optional[Tuple[int, int]]:
    name = Path(p).name
    m = re.match(r"^(\d+)-(\d+)-", name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _prompt(text: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        val = input(f"{text}{suffix}: ").strip()
        if val:
            return val
        if default is not None:
            return default


def _prompt_yes_no(text: str, default: bool = False) -> bool:
    d = "y" if default else "n"
    while True:
        v = input(f"{text} [y/n] [{d}]: ").strip().lower()
        if not v:
            return default
        if v in ("y", "yes"):
            return True
        if v in ("n", "no"):
            return False


def _interactive_wizard(max_retries_default: int) -> argparse.Namespace:
    """Interactive mode used when no flags are provided."""
    print("BMAD Pipeline Interactive Mode")
    print("------------------------------")
    print("Select how you want to run:")
    print("  1) Resume previous run")
    print("  2) Run whole epic")
    print("  3) Run selected stories in an epic")
    print("  4) Run from existing story file (skip create-story)")
    print("  5) Clear saved state")

    choice = _prompt("Choice", "2")
    ns = argparse.Namespace(
        epic=None,
        stories=None,
        whole_epic=False,
        story_file=None,
        resume=False,
        clear=False,
        max_retries=max_retries_default,
        dry_run=False,
    )

    if choice == "1":
        ns.resume = True
        return ns

    if choice == "5":
        ns.clear = True
        return ns

    if choice == "4":
        ns.story_file = _prompt("Story file path")
        ns.dry_run = _prompt_yes_no("Dry run (preview only)?", default=False)
        ns.max_retries = int(_prompt("Max code-review retries", str(max_retries_default)))
        return ns

    # Choices 2 or 3
    ns.epic = int(_prompt("Epic number", "7"))

    if choice == "2":
        ns.whole_epic = True
    elif choice == "3":
        ns.stories = _prompt("Stories selector (e.g. 19-23,25 or 21)")
    else:
        # Default fallback
        ns.whole_epic = True

    ns.dry_run = _prompt_yes_no("Dry run (preview queue and exit)?", default=False)
    ns.max_retries = int(_prompt("Max code-review retries", str(max_retries_default)))
    return ns


def main() -> None:
    parser = argparse.ArgumentParser(description="BMAD pipeline runner via acli rovodev")
    parser.add_argument("--epic", type=int, help="Epic number (e.g. 7)")
    parser.add_argument(
        "--stories",
        type=str,
        help="Story selector within epic (e.g. '21', '19,20,21', '19-23', '19-23,25')",
    )
    parser.add_argument("--whole-epic", action="store_true", help="Run all stories discovered in the epic")
    parser.add_argument("--story-file", type=str, help="Existing story file path (skips create-story)")
    parser.add_argument("--resume", action="store_true", help="Resume from .rovodev/pipeline/state.json")
    parser.add_argument("--clear", action="store_true", help="Clear saved state and exit")
    parser.add_argument("--max-retries", type=int, default=2, help="Max retries for code-review stage")
    parser.add_argument("--dry-run", action="store_true", help="Print planned story queue and exit")

    # If user runs with no flags, go interactive
    if len(sys.argv) == 1:
        args = _interactive_wizard(max_retries_default=2)
    else:
        args = parser.parse_args()

    if args.clear:
        BatchState.clear()
        print("Cleared .rovodev/pipeline/state.json")
        return

    stories_list: Optional[List[int]] = None
    if getattr(args, "stories", None):
        stories_list = parse_story_selector(args.stories)

    pipeline = Pipeline(
        epic=getattr(args, "epic", None),
        stories=stories_list,
        whole_epic=getattr(args, "whole_epic", False),
        resume=getattr(args, "resume", False),
        story_file=getattr(args, "story_file", None),
        max_retries=getattr(args, "max_retries", 2),
    )

    if getattr(args, "dry_run", False):
        st = pipeline.state
        print(f"Pipeline: {st.pipeline_id}")
        print(f"Stories: {len(st.story_queue)}")
        for item in st.story_queue:
            print(f" - {item['story_key']} (epic {item['epic']}, story {item['story']})")
        raise SystemExit(0)

    rc = pipeline.run()
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
