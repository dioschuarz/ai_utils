import os
import yaml
from typing import Dict, List, Tuple
from core.schemas import AdjustmentRule

VALID_METHODOLOGIES = {
    "DCF", "CCA", "ASSET-BASED", "ASSET_BASED", "PTA", "SOTP", "DDM", "NAV", "RIM", 
    "REAL-OPTIONS", "REAL_OPTIONS", "REPLACEMENT", "RDCF", "EV", "DUMMY", "ALL"
}

BAD_WORDS = {"aapl", "ko", "tsla", "jpm", "celsius", "coca-cola", "coca cola"}

def load_thresholds_and_rules(yaml_path: str = None) -> Tuple[Dict, List[AdjustmentRule]]:
    """Loads thresholds and rules from thresholds.yaml."""
    if not yaml_path:
        yaml_path = os.path.join(os.path.dirname(__file__), "thresholds.yaml")
        
    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        
    thresholds = config.get("thresholds", {})
    if "version" in config:
        thresholds["version"] = config["version"]
    raw_rules = config.get("rules", [])
    
    rules = []
    seen_ids = set()
    
    for r in raw_rules:
        rule = AdjustmentRule(**r)
        
        # Validation: Duplicate Rule IDs
        if rule.rule_id in seen_ids:
            raise ValueError(f"Duplicate rule ID detected: {rule.rule_id}")
        seen_ids.add(rule.rule_id)
        
        # Validation: Unsupported Methodology Names
        methodology = rule.affected_methodology.upper().strip()
        if methodology not in VALID_METHODOLOGIES:
            raise ValueError(f"Unsupported methodology name in rule: {rule.affected_methodology}")
            
        # Validation: Ticker symbols / Company names in rule id or description
        rule_id_lower = rule.rule_id.lower()
        desc_lower = rule.description.lower()
        for word in BAD_WORDS:
            if word in rule_id_lower or word in desc_lower:
                raise ValueError(f"Rule {rule.rule_id} contains company-specific pattern: {word}")
                
        rules.append(rule)
        
    # Sort rules deterministically by priority, then rule_id
    rules.sort(key=lambda x: (x.priority, x.rule_id))
    
    return thresholds, rules
