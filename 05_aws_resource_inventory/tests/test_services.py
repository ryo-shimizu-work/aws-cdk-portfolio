"""services.py のARN組み立て・カラム抽出のテスト。"""

from services import (
    SERVICE_DEFINITIONS,
    _ec2_arn, _ebs_arn, _vpc_arn, _sg_arn, _s3_arn,
    _dynamodb_arn, _sqs_arn, _route53_arn, _natgw_arn, _eip_arn,
    _vpce_arn, _tgw_arn, _vpn_arn, _kinesis_arn,
    _apigw_rest_arn, _apigw_http_arn, _opensearch_arn, _tag_name,
)

REGION = "ap-northeast-1"
ACCOUNT = "123456789012"


class TestArnBuilders:
    def test_ec2_arn(self):
        item = {"InstanceId": "i-abc123"}
        assert _ec2_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:instance/i-abc123"

    def test_ebs_arn(self):
        item = {"VolumeId": "vol-abc123"}
        assert _ebs_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:volume/vol-abc123"

    def test_vpc_arn(self):
        item = {"VpcId": "vpc-abc123"}
        assert _vpc_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:vpc/vpc-abc123"

    def test_sg_arn(self):
        item = {"GroupId": "sg-abc123"}
        assert _sg_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:security-group/sg-abc123"

    def test_s3_arn(self):
        item = {"Name": "my-bucket"}
        assert _s3_arn(REGION, ACCOUNT, item) == "arn:aws:s3:::my-bucket"

    def test_dynamodb_arn(self):
        assert _dynamodb_arn(REGION, ACCOUNT, "my-table") == f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/my-table"

    def test_sqs_arn(self):
        url = f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/my-queue"
        assert _sqs_arn(REGION, ACCOUNT, url) == f"arn:aws:sqs:{REGION}:{ACCOUNT}:my-queue"

    def test_route53_arn(self):
        item = {"Id": "/hostedzone/Z1234"}
        assert _route53_arn(REGION, ACCOUNT, item) == "arn:aws:route53:::hostedzone/Z1234"

    def test_natgw_arn(self):
        item = {"NatGatewayId": "nat-abc123"}
        assert _natgw_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:natgateway/nat-abc123"

    def test_eip_arn(self):
        item = {"AllocationId": "eipalloc-abc123"}
        assert _eip_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:elastic-ip/eipalloc-abc123"

    def test_vpce_arn(self):
        item = {"VpcEndpointId": "vpce-abc123"}
        assert _vpce_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:vpc-endpoint/vpce-abc123"

    def test_tgw_arn(self):
        item = {"TransitGatewayId": "tgw-abc123"}
        assert _tgw_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:transit-gateway/tgw-abc123"

    def test_vpn_arn(self):
        item = {"VpnConnectionId": "vpn-abc123"}
        assert _vpn_arn(REGION, ACCOUNT, item) == f"arn:aws:ec2:{REGION}:{ACCOUNT}:vpn-connection/vpn-abc123"

    def test_kinesis_arn(self):
        assert _kinesis_arn(REGION, ACCOUNT, "my-stream") == f"arn:aws:kinesis:{REGION}:{ACCOUNT}:stream/my-stream"

    def test_apigw_rest_arn(self):
        item = {"id": "abc123"}
        assert _apigw_rest_arn(REGION, ACCOUNT, item) == f"arn:aws:apigateway:{REGION}::/restapis/abc123"

    def test_apigw_http_arn(self):
        item = {"ApiId": "abc123"}
        assert _apigw_http_arn(REGION, ACCOUNT, item) == f"arn:aws:apigateway:{REGION}::/apis/abc123"

    def test_opensearch_arn(self):
        item = {"DomainName": "my-domain"}
        assert _opensearch_arn(REGION, ACCOUNT, item) == f"arn:aws:es:{REGION}:{ACCOUNT}:domain/my-domain"


class TestTagName:
    def test_with_name_tag(self):
        resource = {"Tags": [{"Key": "Name", "Value": "web-01"}, {"Key": "Env", "Value": "prod"}]}
        assert _tag_name(resource) == "web-01"

    def test_without_name_tag(self):
        resource = {"Tags": [{"Key": "Env", "Value": "prod"}]}
        assert _tag_name(resource) == ""

    def test_no_tags(self):
        assert _tag_name({}) == ""
        assert _tag_name({"Tags": None}) == ""


class TestServiceDefinitions:
    def test_all_services_have_arn(self):
        for name, defn in SERVICE_DEFINITIONS.items():
            assert "arn" in defn, f"{name} missing 'arn' key"

    def test_all_services_have_required_keys(self):
        required = {"client", "func", "key", "columns"}
        for name, defn in SERVICE_DEFINITIONS.items():
            assert required.issubset(defn.keys()), f"{name} missing keys: {required - defn.keys()}"

    def test_service_count(self):
        assert len(SERVICE_DEFINITIONS) == 40
