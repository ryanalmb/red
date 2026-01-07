from typing import Callable, List
from cyberred.core.models import Finding

# Standard signature for Tier 1 parsers:
# (stdout, stderr, exit_code, agent_id, target) -> List[Finding]
ParserFn = Callable[[str, str, int, str, str], List[Finding]]
