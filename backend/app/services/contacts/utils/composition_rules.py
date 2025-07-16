"""
Composition rules utility functions
Defines rules for component composition and validation
"""

from typing import Dict, List, Any, Set
import structlog

logger = structlog.get_logger(__name__)


def get_personality_appearance_rules() -> Dict[str, List[str]]:
    """
    Get personality-appearance compatibility rules

    Returns:
        Dictionary mapping personality types to compatible appearance types
    """
    return {
        "gentle": ["soft_features", "warm_colors", "elegant_style"],
        "energetic": ["bright_features", "vibrant_colors", "sporty_style"],
        "mysterious": ["sharp_features", "dark_colors", "gothic_style"],
        "cheerful": ["round_features", "bright_colors", "casual_style"],
        "intellectual": ["refined_features", "neutral_colors", "professional_style"],
        "romantic": ["delicate_features", "pastel_colors", "feminine_style"],
    }


def get_skill_compatibility_rules() -> Dict[str, Set[str]]:
    """
    Get skill compatibility rules

    Returns:
        Dictionary mapping skills to incompatible skills
    """
    return {
        "athletic": {"bookworm", "sedentary"},
        "bookworm": {"athletic", "party_lover"},
        "artistic": {"analytical", "technical"},
        "social": {"introverted", "shy"},
        "technical": {"artistic", "emotional"},
        "party_lover": {"bookworm", "introverted"},
    }


def get_rarity_calculation_rules() -> Dict[str, int]:
    """
    Get rarity calculation rules for different component types

    Returns:
        Dictionary mapping component types to rarity multipliers
    """
    return {
        "common_personality": 1,
        "rare_personality": 3,
        "legendary_personality": 5,
        "common_appearance": 1,
        "rare_appearance": 2,
        "legendary_appearance": 4,
        "basic_skill": 1,
        "advanced_skill": 2,
        "master_skill": 3,
    }


def validate_component_compatibility(components: List[Dict[str, Any]]) -> bool:
    """
    Validate that components are compatible with each other

    Args:
        components: List of component dictionaries

    Returns:
        True if all components are compatible, False otherwise
    """
    try:
        # Extract component types and values
        personality_components = [c for c in components if c.get("type") == "personality"]
        appearance_components = [c for c in components if c.get("type") == "appearance"]
        skill_components = [c for c in components if c.get("type") == "skill"]

        # Validate personality-appearance compatibility
        if not _validate_personality_appearance_compatibility(personality_components, appearance_components):
            return False

        # Validate skill compatibility
        if not _validate_skill_compatibility(skill_components):
            return False

        # Validate component limits
        if not _validate_component_limits(components):
            return False

        return True

    except Exception as e:
        logger.error("component_compatibility_validation_error", error=str(e))
        return False


def calculate_template_rarity(components: List[Dict[str, Any]]) -> int:
    """
    Calculate template rarity based on component rarity

    Args:
        components: List of component dictionaries

    Returns:
        Calculated rarity score
    """
    try:
        rarity_rules = get_rarity_calculation_rules()
        total_rarity = 0

        for component in components:
            component_type = component.get("rarity_type", "common")
            rarity_multiplier = rarity_rules.get(component_type, 1)
            component_rarity = component.get("base_rarity", 1)
            total_rarity += component_rarity * rarity_multiplier

        # Apply combination bonus for rare combinations
        combination_bonus = _calculate_combination_bonus(components)
        final_rarity = total_rarity + combination_bonus

        logger.debug(
            "rarity_calculated",
            components_count=len(components),
            base_rarity=total_rarity,
            combination_bonus=combination_bonus,
            final_rarity=final_rarity
        )

        return max(1, final_rarity)  # Minimum rarity of 1

    except Exception as e:
        logger.error("rarity_calculation_error", error=str(e))
        return 1  # Default rarity


def _validate_personality_appearance_compatibility(
    personality_components: List[Dict[str, Any]], 
    appearance_components: List[Dict[str, Any]]
) -> bool:
    """Validate personality-appearance compatibility"""
    if not personality_components or not appearance_components:
        return True  # No conflict if either is empty

    compatibility_rules = get_personality_appearance_rules()
    
    for personality in personality_components:
        personality_type = personality.get("value")
        compatible_appearances = compatibility_rules.get(personality_type, [])
        
        for appearance in appearance_components:
            appearance_type = appearance.get("value")
            if compatible_appearances and appearance_type not in compatible_appearances:
                logger.warning(
                    "personality_appearance_incompatible",
                    personality=personality_type,
                    appearance=appearance_type
                )
                return False
    
    return True


def _validate_skill_compatibility(skill_components: List[Dict[str, Any]]) -> bool:
    """Validate skill compatibility"""
    if len(skill_components) <= 1:
        return True  # No conflict with single or no skills

    incompatibility_rules = get_skill_compatibility_rules()
    skill_values = [skill.get("value") for skill in skill_components]

    for skill in skill_values:
        incompatible_skills = incompatibility_rules.get(skill, set())
        for other_skill in skill_values:
            if other_skill != skill and other_skill in incompatible_skills:
                logger.warning(
                    "skills_incompatible",
                    skill1=skill,
                    skill2=other_skill
                )
                return False

    return True


def _validate_component_limits(components: List[Dict[str, Any]]) -> bool:
    """Validate component count limits"""
    component_counts = {}
    
    for component in components:
        component_type = component.get("type")
        component_counts[component_type] = component_counts.get(component_type, 0) + 1

    # Define limits
    limits = {
        "personality": 1,  # Only one personality
        "appearance": 3,   # Max 3 appearance components
        "skill": 5,        # Max 5 skills
    }

    for component_type, count in component_counts.items():
        limit = limits.get(component_type, 10)  # Default limit
        if count > limit:
            logger.warning(
                "component_limit_exceeded",
                component_type=component_type,
                count=count,
                limit=limit
            )
            return False

    return True


def _calculate_combination_bonus(components: List[Dict[str, Any]]) -> int:
    """Calculate bonus for rare component combinations"""
    # Simple implementation: bonus for having multiple rare components
    rare_count = sum(1 for c in components if c.get("rarity_type", "").startswith("rare"))
    legendary_count = sum(1 for c in components if c.get("rarity_type", "").startswith("legendary"))
    
    bonus = rare_count * 2 + legendary_count * 5
    
    # Extra bonus for full legendary set
    if legendary_count >= 3:
        bonus += 10
    
    return bonus
