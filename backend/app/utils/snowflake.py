"""
Snowflake ID Generator

A distributed unique ID generator based on Twitter's Snowflake algorithm.
Generates 64-bit unique IDs with timestamp, machine ID, and sequence components.
"""

import threading
import time
from typing import TypedDict

from app.utils.logging import get_logger

logger = get_logger(__name__)


class SnowflakeComponents(TypedDict):
    timestamp: int
    datetime: str
    datacenter_id: int
    machine_id: int
    sequence: int


class SnowflakeGenerator:
    """
    Snowflake ID generator for distributed systems.

    ID Structure (64 bits):
    - 1 bit: Sign bit (always 0)
    - 41 bits: Timestamp (milliseconds since epoch)
    - 5 bits: Datacenter ID (0-31)
    - 5 bits: Machine ID (0-31)
    - 12 bits: Sequence number (0-4095)
    """

    # Epoch timestamp (2024-01-01 00:00:00 UTC in milliseconds)
    EPOCH = 1704067200000

    # Bit lengths
    DATACENTER_ID_BITS = 5
    MACHINE_ID_BITS = 5
    SEQUENCE_BITS = 12

    # Maximum values
    MAX_DATACENTER_ID = (1 << DATACENTER_ID_BITS) - 1  # 31
    MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1  # 31
    MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1  # 4095

    # Bit shifts
    MACHINE_ID_SHIFT = SEQUENCE_BITS  # 12
    DATACENTER_ID_SHIFT = SEQUENCE_BITS + MACHINE_ID_BITS  # 17
    TIMESTAMP_SHIFT = SEQUENCE_BITS + MACHINE_ID_BITS + DATACENTER_ID_BITS  # 22

    def __init__(self, datacenter_id: int = 0, machine_id: int = 0) -> None:
        """
        Initialize Snowflake generator.

        Args:
            datacenter_id: Datacenter identifier (0-31)
            machine_id: Machine identifier (0-31)

        Raises:
            ValueError: If datacenter_id or machine_id is out of range
        """
        if not (0 <= datacenter_id <= self.MAX_DATACENTER_ID):
            raise ValueError(f"Datacenter ID must be between 0 and {self.MAX_DATACENTER_ID}")

        if not (0 <= machine_id <= self.MAX_MACHINE_ID):
            raise ValueError(f"Machine ID must be between 0 and {self.MAX_MACHINE_ID}")

        self.datacenter_id = datacenter_id
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

        logger.info(
            "snowflake_generator_initialized",
            datacenter_id=datacenter_id,
            machine_id=machine_id,
            epoch=self.EPOCH,
        )

    def generate_id(self) -> int:
        """
        Generate a unique Snowflake ID.

        Returns:
            int: 64-bit unique identifier

        Raises:
            RuntimeError: If clock moves backwards
        """
        with self.lock:
            timestamp = self._get_timestamp()

            # Handle clock moving backwards
            if timestamp < self.last_timestamp:
                clock_diff = self.last_timestamp - timestamp
                logger.error(
                    "clock_moved_backwards",
                    last_timestamp=self.last_timestamp,
                    current_timestamp=timestamp,
                    diff_ms=clock_diff,
                )
                raise RuntimeError(f"Clock moved backwards by {clock_diff}ms")

            # Same millisecond - increment sequence
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & self.MAX_SEQUENCE

                # Sequence overflow - wait for next millisecond
                if self.sequence == 0:
                    timestamp = self._wait_next_millis(timestamp)
            else:
                # New millisecond - reset sequence
                self.sequence = 0

            self.last_timestamp = timestamp

            # Construct the ID
            return (
                ((timestamp - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.datacenter_id << self.DATACENTER_ID_SHIFT)
                | (self.machine_id << self.MACHINE_ID_SHIFT)
                | self.sequence
            )

    def _get_timestamp(self) -> int:
        """Get current timestamp in milliseconds."""
        return int(time.time() * 1000)

    def _wait_next_millis(self, last_timestamp: int) -> int:
        """Wait until next millisecond."""
        timestamp = self._get_timestamp()
        while timestamp <= last_timestamp:
            timestamp = self._get_timestamp()
        return timestamp

    def parse_id(self, snowflake_id: int) -> SnowflakeComponents:
        """
        Parse a Snowflake ID into its components.

        Args:
            snowflake_id: The Snowflake ID to parse

        Returns:
            dict: Components of the ID (timestamp, datacenter_id, machine_id, sequence)
        """
        timestamp = (snowflake_id >> self.TIMESTAMP_SHIFT) + self.EPOCH
        datacenter_id = (snowflake_id >> self.DATACENTER_ID_SHIFT) & self.MAX_DATACENTER_ID
        machine_id = (snowflake_id >> self.MACHINE_ID_SHIFT) & self.MAX_MACHINE_ID
        sequence = snowflake_id & self.MAX_SEQUENCE

        return {
            "timestamp": timestamp,
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(timestamp / 1000)),
            "datacenter_id": datacenter_id,
            "machine_id": machine_id,
            "sequence": sequence,
        }


# Global instance holder - initialized in main.py or config
_snowflake_state: dict[str, SnowflakeGenerator | None] = {"instance": None}


def init_snowflake(datacenter_id: int = 0, machine_id: int = 0) -> None:
    """
    Initialize the global Snowflake generator.

    Args:
        datacenter_id: Datacenter identifier (0-31)
        machine_id: Machine identifier (0-31)
    """
    _snowflake_state["instance"] = SnowflakeGenerator(datacenter_id, machine_id)
    logger.info("global_snowflake_generator_initialized")


def generate_snowflake_id() -> int:
    """
    Generate a Snowflake ID using the global generator.

    Returns:
        int: 64-bit unique identifier

    Raises:
        RuntimeError: If generator is not initialized
    """
    generator = _snowflake_state["instance"]
    if generator is None:
        raise RuntimeError("Snowflake generator not initialized. Call init_snowflake() first.")

    return generator.generate_id()


def parse_snowflake_id(snowflake_id: int) -> SnowflakeComponents:
    """
    Parse a Snowflake ID using the global generator.

    Args:
        snowflake_id: The Snowflake ID to parse

    Returns:
        dict: Components of the ID

    Raises:
        RuntimeError: If generator is not initialized
    """
    generator = _snowflake_state["instance"]
    if generator is None:
        raise RuntimeError("Snowflake generator not initialized. Call init_snowflake() first.")

    return generator.parse_id(snowflake_id)


def get_snowflake_generator() -> SnowflakeGenerator:
    """
    Get the global Snowflake generator instance.

    Returns:
        SnowflakeGenerator: The global generator instance

    Raises:
        RuntimeError: If generator is not initialized
    """
    generator = _snowflake_state["instance"]
    if generator is None:
        raise RuntimeError("Snowflake generator not initialized. Call init_snowflake() first.")

    return generator
