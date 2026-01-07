from dataclasses import dataclass, asdict
from typing import Any, Optional
import json

@dataclass
class IPCResponse:
    status: str
    request_id: str
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

try:
    response = IPCResponse(status="ok", data={"state": "PAUSED"}, request_id="test-req-id")
    print(f"Response: {response}")
    print(f"JSON: {response.to_json()}")
except Exception as e:
    print(f"Error: {e}")
