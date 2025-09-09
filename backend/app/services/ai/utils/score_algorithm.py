"""
Score offset algorithm implementations.

This module provides various algorithms for calculating score offsets
based on relationship scores. All algorithms maintain initial value as origin
and provide bilateral offset capabilities.
"""

import math
from typing import Dict, Any, Optional
from enums import ScoreOffsetAlgorithm
from utils.logging import get_logger

logger = get_logger(__name__)


class ScoreOffsetCalculator:
    """Score offset calculator with multiple algorithm support."""
    
    # Default parameters for different algorithms
    DEFAULT_PARAMS = {
        ScoreOffsetAlgorithm.NONE: {},
        ScoreOffsetAlgorithm.V1: {
            "k": 100.0,  # Scaling factor
            "max_score": 1000.0,  # Maximum score value
            "min_offset": -500.0,  # Minimum offset value
            "max_offset": 500.0,  # Maximum offset value
        }
    }

    @classmethod
    def calculate_offset(
        self,
        algorithm: int,
        score: float,
        params: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Calculate score offset based on algorithm and parameters.
        
        Args:
            algorithm: Algorithm type from ScoreOffsetAlgorithm enum
            score: Current score value (0-1000)
            params: Algorithm-specific parameters
            
        Returns:
            Calculated offset value
            
        Raises:
            ValueError: If algorithm is unknown or parameters are invalid
        """
        if params is None:
            params = {}
            
        # Merge with default parameters
        algorithm_enum = ScoreOffsetAlgorithm(algorithm)
        default_params = self.DEFAULT_PARAMS.get(algorithm_enum, {})
        merged_params = {**default_params, **params}
        
        try:
            if algorithm_enum == ScoreOffsetAlgorithm.NONE:
                return self._calculate_none_offset(score, merged_params)
            elif algorithm_enum == ScoreOffsetAlgorithm.V1:
                return self._calculate_v1_offset(score, merged_params)
            else:
                raise ValueError(f"Unknown algorithm: {algorithm}")
                
        except Exception as e:
            logger.error(
                "score_offset_calculation_failed",
                algorithm=algorithm,
                score=score,
                params=merged_params,
                error=str(e),
                exc_info=True
            )
            # Return direct mapping as fallback
            return score

    @classmethod
    def _calculate_none_offset(
        self,
        score: float, 
        params: Dict[str, Any]
    ) -> float:
        """
        Direct mapping without any offset.
        
        Args:
            score: Input score (0-1000)
            params: Not used for this algorithm
            
        Returns:
            The same score value
        """
        return score

    @classmethod
    def _calculate_v1_offset(
        self,
        score: float,
        params: Dict[str, Any]
    ) -> float:
        """
        Non-linear offset algorithm using logarithmic function.
        
        Formula: offset = -k * ln(1 - normalized_score)
        Where normalized_score = (score - initial_position) / max_score
        
        This creates a non-linear curve that:
        - Starts at origin (initial_position)
        - Provides bilateral offset (both positive and negative)
        - Has exponential growth characteristics
        
        Args:
            score: Input score (0-1000)
            params: Algorithm parameters containing k, max_score, etc.
            
        Returns:
            Calculated offset value
            
        Raises:
            ValueError: If parameters are invalid
        """
        k = params.get("k", 100.0)
        max_score = params.get("max_score", 1000.0)
        min_offset = params.get("min_offset", -500.0)
        max_offset = params.get("max_offset", 500.0)
        
        # Validate parameters
        if max_score <= 0:
            raise ValueError("max_score must be positive")
        if k <= 0:
            raise ValueError("k must be positive")
            
        # Normalize score to range [-1, 1] with 500 as center (origin)
        center = max_score / 2.0  # 500 for max_score=1000
        normalized_score = (score - center) / (max_score / 2.0)
        
        # Clamp to valid range to avoid math domain errors
        normalized_score = max(-0.999, min(0.999, normalized_score))
        
        try:
            if normalized_score >= 0:
                # Positive direction: -k * ln(1 - normalized_score)
                offset = -k * math.log(1 - normalized_score)
            else:
                # Negative direction: k * ln(1 + normalized_score)
                offset = k * math.log(1 + normalized_score)
                
            # Clamp result to specified bounds
            offset = max(min_offset, min(max_offset, offset))
            
            return center + offset  # Return absolute position, not just offset
            
        except (ValueError, OverflowError) as e:
            logger.warning(
                "v1_algorithm_calculation_error",
                score=score,
                normalized_score=normalized_score,
                error=str(e)
            )
            # Fallback to linear mapping
            return score

    @classmethod
    def get_algorithm_info(self, algorithm: int) -> Dict[str, Any]:
        """
        Get information about a specific algorithm.
        
        Args:
            algorithm: Algorithm type from ScoreOffsetAlgorithm enum
            
        Returns:
            Dictionary containing algorithm information
        """
        algorithm_enum = ScoreOffsetAlgorithm(algorithm)
        
        if algorithm_enum == ScoreOffsetAlgorithm.NONE:
            return {
                "name": "Direct Mapping",
                "description": "No offset applied, direct score mapping",
                "parameters": [],
                "formula": "output = input"
            }
        elif algorithm_enum == ScoreOffsetAlgorithm.V1:
            return {
                "name": "Non-linear Logarithmic",
                "description": "Non-linear offset using logarithmic function with bilateral support",
                "parameters": [
                    {"name": "k", "type": "float", "default": 100.0, "description": "Scaling factor"},
                    {"name": "max_score", "type": "float", "default": 1000.0, "description": "Maximum score value"},
                    {"name": "min_offset", "type": "float", "default": -500.0, "description": "Minimum offset value"},
                    {"name": "max_offset", "type": "float", "default": 500.0, "description": "Maximum offset value"}
                ],
                "formula": "offset = ±k * ln(1 ± normalized_score)"
            }
        else:
            return {
                "name": "Unknown",
                "description": "Unknown algorithm",
                "parameters": [],
                "formula": "N/A"
            }

    @classmethod
    def validate_params(self, algorithm: int, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for a specific algorithm.
        
        Args:
            algorithm: Algorithm type from ScoreOffsetAlgorithm enum
            params: Parameters to validate
            
        Returns:
            True if parameters are valid, False otherwise
        """
        algorithm_enum = ScoreOffsetAlgorithm(algorithm)
        
        if algorithm_enum == ScoreOffsetAlgorithm.NONE:
            # No parameters needed
            return True
        elif algorithm_enum == ScoreOffsetAlgorithm.V1:
            required_params = ["k", "max_score", "min_offset", "max_offset"]
            for param in required_params:
                if param not in params:
                    return False
                if not isinstance(params[param], (int, float)):
                    return False
                if param in ["k", "max_score"] and params[param] <= 0:
                    return False
            return True
        else:
            return False