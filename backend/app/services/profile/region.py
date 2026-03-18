"""Profile region snapshot helpers."""

import re

AUTONOMOUS_DESCRIPTOR_SUFFIXES = (
    "哈萨克",
    "柯尔克孜",
    "蒙古",
    "维吾尔",
    "壮",
    "回",
    "藏",
    "彝",
    "白",
    "傣",
    "苗",
    "羌",
    "土家",
    "哈尼",
    "景颇",
    "朝鲜",
)


def strip_trailing_autonomy_descriptor(raw: str) -> str:
    """Strip repeated trailing ethnic autonomy descriptors from a region name."""
    name = raw.strip()
    changed = True
    while changed and name != "":
        changed = False
        for suffix in AUTONOMOUS_DESCRIPTOR_SUFFIXES:
            suffix_with_zu = f"{suffix}族"
            if name.endswith(suffix_with_zu):
                name = name[: -len(suffix_with_zu)].strip()
                changed = True
                break
        if changed:
            continue
        for suffix in AUTONOMOUS_DESCRIPTOR_SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                changed = True
                break
    return name


def clean_cn_province_name(raw: str) -> str:
    """Normalize a CN province-level name for display."""
    name = raw.strip()
    name = re.sub(r"特别行政区$", "", name)
    name = re.sub(r"省$", "", name)
    name = re.sub(r"市$", "", name)
    name = re.sub(r"(壮族自治区|回族自治区|维吾尔自治区)$", "", name)
    name = re.sub(r"自治区$", "", name)
    return name.strip()


def clean_cn_city_name(raw: str) -> str:
    """Normalize a CN city-level name for display."""
    name = raw.strip()
    name = re.sub(r"自治州$", "", name)
    name = re.sub(r"自治县$", "", name)
    name = re.sub(r"自治旗$", "", name)
    name = re.sub(r"自治市$", "", name)
    name = re.sub(r"市$", "", name)
    name = re.sub(r"地区$", "", name)
    name = re.sub(r"盟$", "", name)
    name = strip_trailing_autonomy_descriptor(name)
    return name.strip()


def build_cn_region_snapshot(province_name: str, city_name: str) -> str:
    """Build the canonical CN region snapshot for profile display."""
    clean_province = clean_cn_province_name(province_name)
    clean_city = clean_cn_city_name(city_name)
    if clean_province == "" or clean_city == "":
        return ""
    if clean_province == clean_city:
        return clean_province
    return f"{clean_province} {clean_city}"
