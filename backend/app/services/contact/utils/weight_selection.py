"""
Weight selection utility functions
Implements weighted random selection algorithms
"""

import random
from typing import List, TypeVar, Protocol
from utils.logging import get_logger

logger = get_logger(__name__)

# Generic type for items that have weight
T = TypeVar("T")


class WeightedItem(Protocol):
    """Protocol for items that can be weighted"""

    weight: int


def weighted_random_selection(items: List[T], limit: int) -> List[T]:
    """
    Perform weighted random selection of items

    Args:
        items: List of items with weight attribute
        limit: Maximum number of items to select

    Returns:
        List of selected items
    """
    if not items:
        return []

    if len(items) <= limit:
        return items

    # Calculate total weight
    total_weight = sum(getattr(item, "weight", 100) for item in items)

    selected = []
    available_items = items.copy()

    for _ in range(min(limit, len(available_items))):
        if not available_items:
            break

        # Generate random number
        rand_num = random.uniform(0, total_weight)

        # Find selected item
        current_weight = 0
        selected_item = None

        for i, item in enumerate(available_items):
            current_weight += getattr(item, "weight", 100)
            if rand_num <= current_weight:
                selected_item = item
                selected.append(item)
                # Remove from available and adjust total weight
                available_items.pop(i)
                total_weight -= getattr(item, "weight", 100)
                break

        # Fallback if no item selected (shouldn't happen)
        if selected_item is None and available_items:
            selected_item = available_items.pop(0)
            selected.append(selected_item)
            total_weight -= getattr(selected_item, "weight", 100)

    logger.debug(
        "weighted_selection_completed", total_items=len(items), selected_count=len(selected), limit=limit
    )

    return selected


def simple_random_selection(items: List[T], limit: int) -> List[T]:
    """
    Perform simple random selection without weights

    Args:
        items: List of items
        limit: Maximum number of items to select

    Returns:
        List of randomly selected items
    """
    if not items:
        return []

    if len(items) <= limit:
        return items

    return random.sample(items, limit)


def calculate_selection_probability(item_weight: int, total_weight: int) -> float:
    """
    Calculate selection probability for an item

    Args:
        item_weight: Weight of the item
        total_weight: Total weight of all items

    Returns:
        Probability as a float between 0 and 1
    """
    if total_weight <= 0:
        return 0.0

    return item_weight / total_weight


def validate_weights(items: List[T]) -> bool:
    """
    Validate that all items have valid weights

    Args:
        items: List of items to validate

    Returns:
        True if all weights are valid, False otherwise
    """
    for item in items:
        weight = getattr(item, "weight", None)
        if weight is None or weight < 0:
            logger.warning("invalid_weight_detected", item=str(item), weight=weight)
            return False

    return True
