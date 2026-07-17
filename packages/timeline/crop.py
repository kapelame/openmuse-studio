from __future__ import annotations


def calculate_center_crop(source_width: int, source_height: int, target_width: int, target_height: int) -> tuple[int, int, int, int]:
    if min(source_width, source_height, target_width, target_height) <= 0:
        raise ValueError("Dimensions must be positive")
    source_ratio = source_width / source_height
    target_ratio = target_width / target_height
    if source_ratio > target_ratio:
        crop_height = source_height
        crop_width = round(source_height * target_ratio)
    else:
        crop_width = source_width
        crop_height = round(source_width / target_ratio)
    left = (source_width - crop_width) // 2
    top = (source_height - crop_height) // 2
    return left, top, left + crop_width, top + crop_height
