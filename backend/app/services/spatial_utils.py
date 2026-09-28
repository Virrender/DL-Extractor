"""
Generic Spatial Math Utilities.

Responsibilities:
- Provide pure-geometry functions to analyze OCRBlock relationships.
- Handle tilt-tolerant horizontal and vertical alignment.
- Sort arbitrary OCR blocks into human reading order (top-to-bottom, left-to-right).
"""

from typing import List
from app.schemas import OCRBlock


def is_horizontally_aligned(anchor: OCRBlock, target: OCRBlock, tolerance_ratio: float = 0.5) -> bool:
    """
    Determines if a target block is on the same horizontal line as the anchor.
    Uses the anchor's height and a tolerance ratio to handle slight tilt/skew.
    
    Args:
        anchor: The reference OCRBlock.
        target: The OCRBlock to check.
        tolerance_ratio: How far the target's center can deviate vertically, 
                         expressed as a fraction of the anchor's height.
    """
    anchor_height = anchor.rect[3] - anchor.rect[1]
    vertical_tolerance = anchor_height * tolerance_ratio
    
    min_y = anchor.center[1] - vertical_tolerance
    max_y = anchor.center[1] + vertical_tolerance
    
    return min_y <= target.center[1] <= max_y


def find_blocks_to_right(
    anchor: OCRBlock, 
    blocks: List[OCRBlock], 
    max_distance: float = float('inf')
) -> List[OCRBlock]:
    """
    Finds all blocks that are horizontally aligned with and to the right of the anchor.
    Returns them sorted by distance from the anchor (closest first).
    """
    aligned_blocks = []
    
    for block in blocks:
        if block is anchor:
            continue
            
        if block.center[0] > anchor.center[0]:
            if is_horizontally_aligned(anchor, block):
                dist = block.rect[0] - anchor.rect[2]
                if dist <= max_distance:
                    aligned_blocks.append(block)
                
    aligned_blocks.sort(key=lambda b: b.rect[0] - anchor.rect[2])
    return aligned_blocks


def find_blocks_below(
    anchor: OCRBlock, 
    blocks: List[OCRBlock], 
    vertical_limit: float = float('inf'),
    require_horizontal_overlap: bool = False,
    overlap_tolerance: float = 30.0
) -> List[OCRBlock]:
    """
    Finds all blocks physically below the anchor.
    Returns them sorted by vertical distance from the anchor (closest first).
    
    Args:
        anchor: The reference block.
        blocks: The list of candidate blocks.
        vertical_limit: Maximum allowed vertical distance from anchor bottom to target top.
        require_horizontal_overlap: If True, candidate must horizontally overlap with anchor
                                    (prevents cross-column contamination in multi-column layouts).
        overlap_tolerance: Allowed horizontal margin when testing overlap.
    """
    below_blocks = []
    
    for block in blocks:
        if block is anchor:
            continue
            
        if block.rect[1] > anchor.center[1]:
            distance = block.rect[1] - anchor.rect[3]
            if distance <= vertical_limit:
                if require_horizontal_overlap:
                    # Overlap occurs if max(x1_a, x1_b) <= min(x2_a, x2_b) + tolerance
                    has_overlap = max(anchor.rect[0], block.rect[0]) <= (min(anchor.rect[2], block.rect[2]) + overlap_tolerance)
                    if not has_overlap:
                        continue
                below_blocks.append(block)
                
    below_blocks.sort(key=lambda b: b.rect[1])
    return below_blocks


def sort_blocks_in_reading_order(blocks: List[OCRBlock], line_tolerance: float = 10.0) -> List[OCRBlock]:
    """
    Sorts OCR blocks top-to-bottom, then left-to-right.
    Groups blocks into "lines" if their vertical top coordinates are within `line_tolerance` pixels.
    """
    if not blocks:
        return []
        
    sorted_by_y = sorted(blocks, key=lambda b: b.rect[1])
    
    lines = []
    current_line = [sorted_by_y[0]]
    current_y = sorted_by_y[0].rect[1]
    
    for block in sorted_by_y[1:]:
        if abs(block.rect[1] - current_y) <= line_tolerance:
            current_line.append(block)
        else:
            lines.append(current_line)
            current_line = [block]
            current_y = block.rect[1]
            
    if current_line:
        lines.append(current_line)
        
    sorted_blocks = []
    for line in lines:
        sorted_line = sorted(line, key=lambda b: b.rect[0])
        sorted_blocks.extend(sorted_line)
        
    return sorted_blocks