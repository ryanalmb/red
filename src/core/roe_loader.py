import yaml
import os
import logging

class RoELoader:
    DEFAULT_ROE = {
        "allowed_ips": ["127.0.0.1"],
        "forbidden_ports": [21, 23], # FTP, Telnet usually noisy/honeyports
        "aggression_level": "LOW",
        "semantic_rules": "Do not cause Denial of Service. Do not delete data.",
        "require_authorization": True  # New: Enable HITL authorization
    }

    def __init__(self, config_path="config/roe.yaml"):
        self.config_path = config_path
        self.logger = logging.getLogger("RoELoader")
        self._roe = None
        self._session_allowed = set()  # Dynamic session-based authorizations
        self._always_allowed = set()   # Permanently authorized (persisted)

    def load(self) -> dict:
        """Loads RoE from YAML or returns default."""
        if not os.path.exists(self.config_path):
            self.logger.warning(f"RoE file not found at {self.config_path}. Using Defaults.")
            self._create_default()
            self._roe = self.DEFAULT_ROE.copy()
        else:
            try:
                with open(self.config_path, 'r') as f:
                    self._roe = yaml.safe_load(f)
                    self._validate(self._roe)
                    self.logger.info("Rules of Engagement Loaded.")
            except Exception as e:
                self.logger.error(f"Failed to load RoE: {e}. Aborting to Safe Mode.")
                self._roe = self.DEFAULT_ROE.copy()
        
        # Pre-populate session allowed from config
        for ip in self._roe.get("allowed_ips", []):
            self._session_allowed.add(ip)
        
        return self._roe

    def is_target_allowed(self, target: str) -> bool:
        """Check if a target IP/hostname is authorized."""
        # Strip protocol and path if present
        clean_target = target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        
        # Check session allowed (includes config + dynamically authorized)
        if clean_target in self._session_allowed:
            return True
        
        # Check always allowed (persisted)
        if clean_target in self._always_allowed:
            return True
        
        return False

    def authorize_target(self, target: str, persist: bool = False) -> None:
        """Dynamically authorize a target for this session."""
        clean_target = target.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        
        self._session_allowed.add(clean_target)
        self.logger.info(f"Target {clean_target} authorized for session.")
        
        if persist:
            self._always_allowed.add(clean_target)
            self._persist_target(clean_target)
            self.logger.info(f"Target {clean_target} added to permanent allow list.")

    def _persist_target(self, target: str) -> None:
        """Persist a new target to the RoE config file."""
        try:
            if self._roe is None:
                self.load()
            
            if "allowed_ips" not in self._roe:
                self._roe["allowed_ips"] = []
            
            if target not in self._roe["allowed_ips"]:
                self._roe["allowed_ips"].append(target)
                
                with open(self.config_path, 'w') as f:
                    yaml.dump(self._roe, f, default_flow_style=False)
                    
        except Exception as e:
            self.logger.error(f"Could not persist target to RoE: {e}")

    def requires_authorization(self) -> bool:
        """Check if HITL authorization is enabled."""
        if self._roe is None:
            return True
        return self._roe.get("require_authorization", True)

    def _create_default(self):
        """Creates a default RoE file for the user to edit."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                yaml.dump(self.DEFAULT_ROE, f, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"Could not create default RoE: {e}")

    def _validate(self, roe):
        """Basic schema validation."""
        required = ["allowed_ips", "forbidden_ports"]
        for key in required:
            if key not in roe:
                raise ValueError(f"RoE missing required key: {key}")

