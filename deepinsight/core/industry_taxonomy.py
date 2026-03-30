PRIMARY_INDUSTRY_NAME = "医药生物"

INDUSTRY_RULES = [
    ("医疗器械", ["医疗", "器械", "诊断", "体外", "医学影像", "影像", "牙科", "义齿", "耗材"]),
    ("医药商业", ["医药商业", "药房", "药店", "流通", "零售", "商业"]),
    ("中药", ["中药", "中成药", "饮片"]),
    ("生物制品", ["生物", "血制品", "疫苗", "细胞", "基因"]),
    ("医药服务", ["CRO", "CDMO", "研发服务", "医疗服务", "医院", "健康"]),
    ("化学制药", ["制药", "药业", "药", "原料药", "创新药"]),
]


def infer_industry_name(company_name: str | None, explicit_industry_name: str | None = None) -> str | None:
    if explicit_industry_name:
        return explicit_industry_name
    normalized = (company_name or "").strip()
    if not normalized:
        return None
    for industry_name, keywords in INDUSTRY_RULES:
        if any(keyword in normalized for keyword in keywords):
            return industry_name
    return PRIMARY_INDUSTRY_NAME


def infer_industry_path(company_name: str | None, explicit_industry_name: str | None = None) -> list[str]:
    industry_name = infer_industry_name(company_name, explicit_industry_name)
    if not industry_name:
        return []
    if industry_name == PRIMARY_INDUSTRY_NAME:
        return [PRIMARY_INDUSTRY_NAME]
    return [PRIMARY_INDUSTRY_NAME, industry_name]
