"""
Drug Interaction Checker
========================
Checks for interactions between drugs using a local database.
"""


import json
import os
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DrugInteractionChecker:
    """
    Checks for drug-drug interactions.
    """
    
    def __init__(self, interactions_file: str = None):
        if interactions_file is None:
            # Default path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            interactions_file = os.path.join(base_dir, "data", "interactions.json")
            
        self.interactions_db = self._load_interactions(interactions_file)
        
    def _load_interactions(self, path: str) -> List[Dict[str, Any]]:
        """Load interactions from JSON file."""
        if not os.path.exists(path):
            logger.warning(f"Interactions file not found at {path}")
            return []
            
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data.get("interactions", [])
        except Exception as e:
            logger.error(f"Failed to load interactions: {e}")
            return []
            
    def check_interactions(self, drugs: List[str]) -> List[Dict[str, Any]]:
        """
        Check for interactions between a list of drugs.
        
        Args:
            drugs: List of drug names
            
        Returns:
            List of interaction details
        """
        found_interactions = []
        drugs_lower = [d.lower() for d in drugs]
        
        # Simple O(N^2) check against DB (DB is small enough)
        # For larger DB, we would index by drug name
        
        # Create a set for faster lookup if needed, but we need to match pairs
        # Let's index the DB by drug_a and drug_b for faster lookup
        
        for interaction in self.interactions_db:
            drug_a = interaction.get("drug_a", "").lower()
            drug_b = interaction.get("drug_b", "").lower()
            
            if drug_a in drugs_lower and drug_b in drugs_lower:
                found_interactions.append(interaction)
                
        return found_interactions

# Singleton
_interaction_checker = None

def get_drug_interaction_checker() -> DrugInteractionChecker:
    global _interaction_checker
    if _interaction_checker is None:
        _interaction_checker = DrugInteractionChecker()
    return _interaction_checker
