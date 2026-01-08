"""Tests for Snowflake ID generator."""

import time

import pytest

from app.utils.snowflake import SnowflakeGenerator, generate_snowflake_id


def test_snowflake_generator_initialization() -> None:
    """Test SnowflakeGenerator initialization with valid parameters."""
    generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)
    assert generator.datacenter_id == 1
    assert generator.machine_id == 1
    assert generator.sequence == 0


def test_snowflake_generator_invalid_datacenter_id() -> None:
    """Test SnowflakeGenerator raises error for invalid datacenter_id."""
    with pytest.raises(ValueError, match="Datacenter ID must be between 0 and 31"):
        SnowflakeGenerator(datacenter_id=32, machine_id=1)

    with pytest.raises(ValueError, match="Datacenter ID must be between 0 and 31"):
        SnowflakeGenerator(datacenter_id=-1, machine_id=1)


def test_snowflake_generator_invalid_machine_id() -> None:
    """Test SnowflakeGenerator raises error for invalid machine_id."""
    with pytest.raises(ValueError, match="Machine ID must be between 0 and 31"):
        SnowflakeGenerator(datacenter_id=1, machine_id=32)

    with pytest.raises(ValueError, match="Machine ID must be between 0 and 31"):
        SnowflakeGenerator(datacenter_id=1, machine_id=-1)


def test_snowflake_id_generation() -> None:
    """Test ID generation produces unique IDs."""
    generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)

    # Generate multiple IDs
    ids = [generator.generate_id() for _ in range(100)]

    # All IDs should be unique
    assert len(ids) == len(set(ids))

    # All IDs should be positive integers
    assert all(isinstance(id_, int) and id_ > 0 for id_ in ids)


def test_snowflake_id_monotonicity() -> None:
    """Test that IDs are monotonically increasing within same millisecond."""
    generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)

    # Generate IDs rapidly
    ids = [generator.generate_id() for _ in range(10)]

    # IDs should be in ascending order
    assert ids == sorted(ids)


def test_snowflake_id_components() -> None:
    """Test that ID components are correctly encoded."""
    datacenter_id = 5
    machine_id = 10
    generator = SnowflakeGenerator(datacenter_id=datacenter_id, machine_id=machine_id)

    id_ = generator.generate_id()

    # Extract components from ID
    # Snowflake ID structure: [timestamp(41 bits)][datacenter(5 bits)]
    # [machine(5 bits)][sequence(12 bits)]
    extracted_sequence = id_ & 0xFFF  # Last 12 bits
    extracted_machine = (id_ >> 12) & 0x1F  # Next 5 bits
    extracted_datacenter = (id_ >> 17) & 0x1F  # Next 5 bits

    assert extracted_datacenter == datacenter_id
    assert extracted_machine == machine_id
    assert 0 <= extracted_sequence < 4096


def test_snowflake_id_timestamp() -> None:
    """Test that timestamp component in ID is reasonable."""
    generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)

    # Get timestamp relative to custom epoch (not wall clock time)
    custom_epoch = 1704067200000  # 2024-01-01 00:00:00 UTC in milliseconds
    before = int(time.time() * 1000) - custom_epoch
    id_ = generator.generate_id()
    after = int(time.time() * 1000) - custom_epoch

    # Extract timestamp from ID (41 bits, shifted by 22 bits)
    # This is time since custom epoch, not wall clock time
    extracted_timestamp = id_ >> 22

    # Allow 1ms tolerance due to timing variations
    assert before <= extracted_timestamp <= after + 1


def test_global_snowflake_initialization() -> None:
    """Test global snowflake generator initialization."""
    # init_snowflake is already called in conftest.py
    # Just test that generate_snowflake_id works
    id_ = generate_snowflake_id()

    assert isinstance(id_, int)
    assert id_ > 0


def test_global_snowflake_generates_unique_ids() -> None:
    """Test that global generator produces unique IDs."""
    ids = [generate_snowflake_id() for _ in range(100)]

    # All IDs should be unique
    assert len(ids) == len(set(ids))

    # IDs should be in ascending order (mostly, allowing for clock adjustments)
    assert sorted(ids) == ids


def test_snowflake_sequence_rollover() -> None:
    """Test that sequence counter rolls over correctly within same millisecond."""
    generator = SnowflakeGenerator(datacenter_id=1, machine_id=1)

    # Manually set timestamp to same value to force sequence increment
    current_ts = int(time.time() * 1000)
    generator.last_timestamp = current_ts
    generator.sequence = 4095  # Max sequence value

    # Next ID generation should wait for next millisecond
    # or rollover sequence (implementation dependent)
    id1 = generator.generate_id()
    id2 = generator.generate_id()

    assert id2 > id1
