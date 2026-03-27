"""
未使用・無駄リソースの検出ルール。
各ルールはサービス名をキーに、(row, raw_item) -> warning文字列 or None を返す関数。
"""


def _ec2_warnings(row, raw):
    state = row.get("State", "")
    if state == "stopped":
        return "⚠️ 停止中 (課金: EBS・EIP継続)"
    if state == "terminated":
        return None  # terminatedは無視
    return None


def _ebs_warnings(row, raw):
    if row.get("State") == "available":
        size = row.get("Size(GiB)", "?")
        return f"⚠️ 未アタッチ ({size}GiB課金中)"
    return None


def _eip_warnings(row, raw):
    if "(未割当)" in str(row.get("AssociationId", "")):
        return "⚠️ 未割当 ($0.005/hr課金中)"
    return None


def _natgw_warnings(row, raw):
    state = row.get("State", "")
    if state == "failed":
        return "⚠️ 失敗状態"
    return None


def _rds_warnings(row, raw):
    if row.get("Status") == "stopped":
        return "⚠️ 停止中 (7日後に自動起動)"
    return None


def _elb_warnings(row, raw):
    if row.get("State") == "failed":
        return "⚠️ 失敗状態"
    return None


def _sg_warnings(row, raw):
    # VpcIdが空 = EC2-Classic (レガシー)
    if not row.get("VpcId"):
        return "⚠️ EC2-Classic SG (レガシー)"
    return None


def _snapshot_warnings(row, raw):
    if row.get("Status") == "completed":
        size = row.get("Size(GiB)", "?")
        return f"💡 手動スナップショット ({size}GiB保存課金)"
    return None


WARNING_RULES = {
    "EC2 Instances": _ec2_warnings,
    "EBS Volumes": _ebs_warnings,
    "Elastic IPs": _eip_warnings,
    "NAT Gateways": _natgw_warnings,
    "RDS Instances": _rds_warnings,
    "ELBv2 (ALB/NLB)": _elb_warnings,
    "Security Groups": _sg_warnings,
    "RDS Snapshots (Manual)": _snapshot_warnings,
}


def check_warnings(svc_name, rows, raw_items):
    """各リソースにwarningを付与。warningがあるrowのリストを返す。"""
    rule = WARNING_RULES.get(svc_name)
    if not rule:
        return []

    warnings = []
    for row, raw in zip(rows, raw_items):
        msg = rule(row, raw)
        if msg:
            warnings.append({**row, "Warning": msg})
    return warnings
