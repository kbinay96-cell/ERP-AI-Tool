import os
from code_block_applier import parse_code_blocks, apply_all_blocks

def test_parse_and_apply_create(tmp_path):
    sample = """### FILE: test_sample.txt
### ACTION: create
<<<CODE_START>>>
hello world
<<<CODE_END>>>
"""
    blocks = parse_code_blocks(sample)
    assert len(blocks) == 1
    results = apply_all_blocks(str(tmp_path), sample)
    assert results and results[0].success
    created = tmp_path / "test_sample.txt"
    assert created.exists()
    assert created.read_text().strip() == "hello world"