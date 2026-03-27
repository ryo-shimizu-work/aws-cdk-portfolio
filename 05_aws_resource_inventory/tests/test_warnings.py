"""resource_warnings.py のテスト。"""

from resource_warnings import check_warnings, WARNING_RULES


class TestEc2Warnings:
    def test_stopped_instance(self):
        rows = [{"State": "stopped", "InstanceId": "i-123"}]
        result = check_warnings("EC2 Instances", rows, [{}])
        assert len(result) == 1
        assert "停止中" in result[0]["Warning"]

    def test_running_instance_no_warning(self):
        rows = [{"State": "running", "InstanceId": "i-123"}]
        assert check_warnings("EC2 Instances", rows, [{}]) == []

    def test_terminated_instance_no_warning(self):
        rows = [{"State": "terminated", "InstanceId": "i-123"}]
        assert check_warnings("EC2 Instances", rows, [{}]) == []


class TestEbsWarnings:
    def test_available_volume(self):
        rows = [{"State": "available", "VolumeId": "vol-123", "Size(GiB)": 100}]
        result = check_warnings("EBS Volumes", rows, [{}])
        assert len(result) == 1
        assert "未アタッチ" in result[0]["Warning"]
        assert "100" in result[0]["Warning"]

    def test_in_use_volume_no_warning(self):
        rows = [{"State": "in-use", "VolumeId": "vol-123"}]
        assert check_warnings("EBS Volumes", rows, [{}]) == []


class TestEipWarnings:
    def test_unassociated_eip(self):
        rows = [{"PublicIp": "1.2.3.4", "AssociationId": "(未割当)"}]
        result = check_warnings("Elastic IPs", rows, [{}])
        assert len(result) == 1
        assert "未割当" in result[0]["Warning"]

    def test_associated_eip_no_warning(self):
        rows = [{"PublicIp": "1.2.3.4", "AssociationId": "eipassoc-123"}]
        assert check_warnings("Elastic IPs", rows, [{}]) == []


class TestNatGwWarnings:
    def test_failed_natgw(self):
        rows = [{"State": "failed", "NatGatewayId": "nat-123"}]
        result = check_warnings("NAT Gateways", rows, [{}])
        assert len(result) == 1

    def test_available_natgw_no_warning(self):
        rows = [{"State": "available", "NatGatewayId": "nat-123"}]
        assert check_warnings("NAT Gateways", rows, [{}]) == []


class TestRdsWarnings:
    def test_stopped_rds(self):
        rows = [{"Status": "stopped", "DBInstanceId": "mydb"}]
        result = check_warnings("RDS Instances", rows, [{}])
        assert len(result) == 1
        assert "7日後" in result[0]["Warning"]

    def test_available_rds_no_warning(self):
        rows = [{"Status": "available", "DBInstanceId": "mydb"}]
        assert check_warnings("RDS Instances", rows, [{}]) == []


class TestSnapshotWarnings:
    def test_completed_snapshot(self):
        rows = [{"Status": "completed", "Size(GiB)": 50, "SnapshotId": "snap-123"}]
        result = check_warnings("RDS Snapshots (Manual)", rows, [{}])
        assert len(result) == 1
        assert "手動スナップショット" in result[0]["Warning"]


class TestNoRuleService:
    def test_unknown_service_returns_empty(self):
        assert check_warnings("Unknown Service", [{"foo": "bar"}], [{}]) == []

    def test_lambda_no_warnings(self):
        rows = [{"FunctionName": "my-func"}]
        assert check_warnings("Lambda Functions", rows, [{}]) == []


class TestWarningRulesCompleteness:
    def test_rule_count(self):
        assert len(WARNING_RULES) == 8
