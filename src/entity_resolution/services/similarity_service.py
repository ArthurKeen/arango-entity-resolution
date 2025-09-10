"""
Similarity Service for Entity Resolution

Handles similarity computation using:
- Fellegi-Sunter probabilistic framework
- ArangoDB native similarity functions
- Foxx service integration (when available)
- Fallback to Python implementation
"""

import requests
import math
from typing import Dict, List, Any, Optional
from ..utils.config import Config, get_config
from ..utils.logging import get_logger


class SimilarityService:
    """
    Similarity computation service using Fellegi-Sunter framework
    
    Can work in two modes:
    1. Foxx service mode: Uses ArangoDB native similarity functions
    2. Python mode: Fallback implementation with Python similarity functions
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self.logger = get_logger(__name__)
        self.foxx_available = False
        
    def connect(self) -> bool:
        """Test connection to Foxx services if enabled"""
        if not self.config.er.enable_foxx_services:
            self.logger.info("Foxx services disabled, using Python fallback")
            return True
        
        try:
            # Test Foxx service availability
            url = self.config.get_foxx_service_url("health")
            response = requests.get(url, auth=self.config.get_auth_tuple(), timeout=5)
            
            if response.status_code == 200:
                self.foxx_available = True
                self.logger.info("Foxx similarity service available")
            else:
                self.logger.warning("Foxx service not available, using Python fallback")
                
        except Exception as e:
            self.logger.warning(f"Cannot connect to Foxx services: {e}")
        
        return True
    
    def compute_similarity(self, doc_a: Dict[str, Any], doc_b: Dict[str, Any],
                          field_weights: Optional[Dict[str, Any]] = None,
                          include_details: bool = False) -> Dict[str, Any]:
        """
        Compute similarity score between two documents
        
        Args:
            doc_a: First document
            doc_b: Second document  
            field_weights: Field-specific weights for Fellegi-Sunter
            include_details: Whether to include detailed field scores
            
        Returns:
            Similarity computation results
        """
        field_weights = field_weights or self.get_default_field_weights()
        
        if self.foxx_available:
            return self._compute_via_foxx(doc_a, doc_b, field_weights, include_details)
        else:
            return self._compute_via_python(doc_a, doc_b, field_weights, include_details)
    
    def compute_batch_similarity(self, pairs: List[Dict[str, Any]],
                                field_weights: Optional[Dict[str, Any]] = None,
                                include_details: bool = False) -> Dict[str, Any]:
        """
        Compute similarity for multiple document pairs
        
        Args:
            pairs: List of document pairs to compare
            field_weights: Field-specific weights
            include_details: Whether to include detailed scores
            
        Returns:
            Batch similarity results
        """
        field_weights = field_weights or self.get_default_field_weights()
        
        if self.foxx_available:
            return self._compute_batch_via_foxx(pairs, field_weights, include_details)
        else:
            return self._compute_batch_via_python(pairs, field_weights, include_details)
    
    def get_default_field_weights(self) -> Dict[str, Any]:
        """Get default Fellegi-Sunter field weights"""
        return {
            # Name fields
            "name_ngram": {
                "m_prob": 0.9,
                "u_prob": 0.01,
                "threshold": 0.7,
                "importance": 1.0
            },
            "first_name_ngram": {
                "m_prob": 0.85,
                "u_prob": 0.02,
                "threshold": 0.7,
                "importance": 0.8
            },
            "last_name_ngram": {
                "m_prob": 0.9,
                "u_prob": 0.015,
                "threshold": 0.7,
                "importance": 1.0
            },
            "first_name_levenshtein": {
                "m_prob": 0.8,
                "u_prob": 0.05,
                "threshold": 0.6,
                "importance": 0.7
            },
            "last_name_levenshtein": {
                "m_prob": 0.85,
                "u_prob": 0.03,
                "threshold": 0.6,
                "importance": 0.9
            },
            
            # Address fields
            "address_ngram": {
                "m_prob": 0.8,
                "u_prob": 0.03,
                "threshold": 0.6,
                "importance": 0.8
            },
            "city_ngram": {
                "m_prob": 0.9,
                "u_prob": 0.05,
                "threshold": 0.8,
                "importance": 0.6
            },
            
            # Exact match fields
            "email_exact": {
                "m_prob": 0.95,
                "u_prob": 0.001,
                "threshold": 1.0,
                "importance": 1.2
            },
            "phone_exact": {
                "m_prob": 0.9,
                "u_prob": 0.005,
                "threshold": 1.0,
                "importance": 1.1
            },
            
            # Company field
            "company_ngram": {
                "m_prob": 0.8,
                "u_prob": 0.02,
                "threshold": 0.7,
                "importance": 0.7
            },
            
            # Global thresholds
            "global": {
                "upper_threshold": 2.0,   # Clear match
                "lower_threshold": -1.0   # Clear non-match
            }
        }
    
    def _compute_via_foxx(self, doc_a: Dict[str, Any], doc_b: Dict[str, Any],
                         field_weights: Dict[str, Any], include_details: bool) -> Dict[str, Any]:
        """Compute similarity via Foxx service"""
        try:
            url = self.config.get_foxx_service_url("similarity/compute")
            
            payload = {
                "docA": doc_a,
                "docB": doc_b,
                "fieldWeights": field_weights,
                "includeDetails": include_details
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("similarity", {})
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx similarity computation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _compute_via_python(self, doc_a: Dict[str, Any], doc_b: Dict[str, Any],
                           field_weights: Dict[str, Any], include_details: bool) -> Dict[str, Any]:
        """Compute similarity via Python implementation"""
        try:
            # Compute individual field similarities
            similarities = {}
            
            # Name comparisons
            full_name_a = f"{doc_a.get('first_name', '')} {doc_a.get('last_name', '')}".strip()
            full_name_b = f"{doc_b.get('first_name', '')} {doc_b.get('last_name', '')}".strip()
            
            if full_name_a and full_name_b:
                similarities["name_ngram"] = self._ngram_similarity(full_name_a, full_name_b)
            
            # Individual name fields
            if doc_a.get('first_name') and doc_b.get('first_name'):
                similarities["first_name_ngram"] = self._ngram_similarity(
                    doc_a['first_name'], doc_b['first_name'])
                similarities["first_name_levenshtein"] = self._normalized_levenshtein(
                    doc_a['first_name'], doc_b['first_name'])
            
            if doc_a.get('last_name') and doc_b.get('last_name'):
                similarities["last_name_ngram"] = self._ngram_similarity(
                    doc_a['last_name'], doc_b['last_name'])
                similarities["last_name_levenshtein"] = self._normalized_levenshtein(
                    doc_a['last_name'], doc_b['last_name'])
            
            # Address comparisons
            if doc_a.get('address') and doc_b.get('address'):
                similarities["address_ngram"] = self._ngram_similarity(
                    doc_a['address'], doc_b['address'])
            
            if doc_a.get('city') and doc_b.get('city'):
                similarities["city_ngram"] = self._ngram_similarity(
                    doc_a['city'], doc_b['city'])
            
            # Exact match fields
            similarities["email_exact"] = 1.0 if (doc_a.get('email') and doc_b.get('email') and 
                                                 doc_a['email'].lower() == doc_b['email'].lower()) else 0.0
            similarities["phone_exact"] = 1.0 if (doc_a.get('phone') and doc_b.get('phone') and 
                                                 doc_a['phone'] == doc_b['phone']) else 0.0
            
            # Company comparison
            if doc_a.get('company') and doc_b.get('company'):
                similarities["company_ngram"] = self._ngram_similarity(
                    doc_a['company'], doc_b['company'])
            
            # Apply Fellegi-Sunter framework
            result = self._compute_fellegi_sunter_score(similarities, field_weights, include_details)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Python similarity computation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _compute_batch_via_foxx(self, pairs: List[Dict[str, Any]],
                               field_weights: Dict[str, Any], include_details: bool) -> Dict[str, Any]:
        """Compute batch similarity via Foxx service"""
        try:
            url = self.config.get_foxx_service_url("similarity/batch")
            
            payload = {
                "pairs": pairs,
                "fieldWeights": field_weights,
                "includeDetails": include_details
            }
            
            response = requests.post(
                url,
                auth=self.config.get_auth_tuple(),
                json=payload,
                timeout=self.config.er.foxx_timeout * 2  # Longer timeout for batch
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"Foxx service returned {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"Foxx batch similarity computation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _compute_batch_via_python(self, pairs: List[Dict[str, Any]],
                                 field_weights: Dict[str, Any], include_details: bool) -> Dict[str, Any]:
        """Compute batch similarity via Python implementation"""
        try:
            results = []
            
            for i, pair in enumerate(pairs):
                doc_a = pair.get("docA") or pair.get("record_a")
                doc_b = pair.get("docB") or pair.get("record_b")
                
                if not doc_a or not doc_b:
                    results.append({
                        "success": False,
                        "error": f"Missing documents in pair {i}",
                        "pair_index": i
                    })
                    continue
                
                similarity = self._compute_via_python(doc_a, doc_b, field_weights, include_details)
                similarity["pair_index"] = i
                results.append(similarity)
            
            successful_results = [r for r in results if r.get("success", True)]
            
            return {
                "success": True,
                "method": "python",
                "results": results,
                "statistics": {
                    "total_pairs": len(pairs),
                    "successful_pairs": len(successful_results),
                    "failed_pairs": len(pairs) - len(successful_results),
                    "average_score": sum(r.get("total_score", 0) for r in successful_results) / len(successful_results) if successful_results else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Python batch similarity computation failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _ngram_similarity(self, str1: str, str2: str, n: int = 3) -> float:
        """Calculate n-gram similarity between two strings"""
        if not str1 or not str2:
            return 0.0
        
        str1 = str1.lower().strip()
        str2 = str2.lower().strip()
        
        if str1 == str2:
            return 1.0
        
        # Generate n-grams
        ngrams1 = set(str1[i:i+n] for i in range(len(str1)-n+1))
        ngrams2 = set(str2[i:i+n] for i in range(len(str2)-n+1))
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1.intersection(ngrams2))
        union = len(ngrams1.union(ngrams2))
        
        return intersection / union if union > 0 else 0.0
    
    def _normalized_levenshtein(self, str1: str, str2: str) -> float:
        """Calculate normalized Levenshtein distance (1 - distance/max_length)"""
        if not str1 or not str2:
            return 0.0
        
        if str1 == str2:
            return 1.0
        
        distance = self._levenshtein_distance(str1, str2)
        max_length = max(len(str1), len(str2))
        
        return 1 - (distance / max_length) if max_length > 0 else 0.0
    
    def _levenshtein_distance(self, str1: str, str2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if not str1:
            return len(str2)
        if not str2:
            return len(str1)
        
        # Create distance matrix
        matrix = [[0] * (len(str2) + 1) for _ in range(len(str1) + 1)]
        
        # Initialize first row and column
        for i in range(len(str1) + 1):
            matrix[i][0] = i
        for j in range(len(str2) + 1):
            matrix[0][j] = j
        
        # Fill matrix
        for i in range(1, len(str1) + 1):
            for j in range(1, len(str2) + 1):
                if str1[i-1] == str2[j-1]:
                    cost = 0
                else:
                    cost = 1
                
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )
        
        return matrix[len(str1)][len(str2)]
    
    def _compute_fellegi_sunter_score(self, similarities: Dict[str, float],
                                     field_weights: Dict[str, Any], 
                                     include_details: bool = False) -> Dict[str, Any]:
        """Apply Fellegi-Sunter probabilistic framework"""
        total_score = 0
        field_scores = {}
        
        for field, sim_value in similarities.items():
            if field in field_weights:
                weights = field_weights[field]
                threshold = weights.get("threshold", 0.5)
                agreement = sim_value > threshold
                
                # Fellegi-Sunter log-likelihood ratio
                m_prob = weights.get("m_prob", 0.8)
                u_prob = weights.get("u_prob", 0.05)
                
                if agreement:
                    weight = math.log(m_prob / u_prob)
                else:
                    weight = math.log((1 - m_prob) / (1 - u_prob))
                
                field_scores[field] = {
                    "similarity": sim_value,
                    "agreement": agreement,
                    "weight": weight,
                    "threshold": threshold
                }
                
                # Add field importance multiplier
                importance = weights.get("importance", 1.0)
                total_score += weight * importance
        
        # Calculate confidence and match decision
        global_weights = field_weights.get("global", {})
        upper_threshold = global_weights.get("upper_threshold", 2.0)
        lower_threshold = global_weights.get("lower_threshold", -1.0)
        
        is_match = total_score > upper_threshold
        is_possible_match = total_score > lower_threshold and total_score <= upper_threshold
        
        confidence = min(max(
            (total_score - lower_threshold) / (upper_threshold - lower_threshold), 
            0
        ), 1)
        
        result = {
            "total_score": total_score,
            "is_match": is_match,
            "is_possible_match": is_possible_match,
            "confidence": confidence,
            "decision": "match" if is_match else ("possible_match" if is_possible_match else "non_match")
        }
        
        if include_details:
            result["field_scores"] = field_scores
            result["thresholds"] = global_weights
        
        return result
