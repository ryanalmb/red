import yaml
import os
import logging

class RoELoader:
    DEFAULT_ROE = {
        "allowed_ips": ["127.0.0.1"],
        "forbidden_ports": [21, 23], # FTP, Telnet usually noisy/honeyports
        "aggression_level": "LOW",
        "semantic_rules": "Do not cause Denial of Service. Do not delete data."
    }

    def __init__(self, config_path="config/roe.yaml"):
        self.config_path = config_path
        self.logger = logging.getLogger("RoELoader")

    def load(self) -> dict:
        """Loads RoE from YAML or returns default."""
        if not os.path.exists(self.config_path):
            self.logger.warning(f"RoE file not found at {self.config_path}. Using Defaults.")
            self._create_default()
            return self.DEFAULT_ROE
        
        try:
            with open(self.config_path, 'r') as f:
                roe = yaml.safe_load(f)
                self._validate(roe)
                self.logger.info("Rules of Engagement Loaded.")
                return roe
        except Exception as e:
            self.logger.error(f"Failed to load RoE: {e}. Aborting to Safe Mode.")
            return self.DEFAULT_ROE

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
