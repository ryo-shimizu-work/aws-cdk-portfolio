"""
サービスごとのリソース取得定義。
各エントリ:
  - client: boto3クライアント名
  - func: 呼び出すメソッド名
  - key: レスポンスからリソースリストを取り出すキー
  - columns: 出力する列 (lambda or キー名)
  - is_global: リージョン非依存(us-east-1固定)かどうか
  - arn: ARN取得方法 (キー名 / lambda / None=columns内で既に含む)
"""


def _tag_name(resource):
    for tag in resource.get("Tags") or []:
        if tag["Key"] == "Name":
            return tag["Value"]
    return ""


def _ec2_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:instance/{item['InstanceId']}"


def _ebs_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:volume/{item['VolumeId']}"


def _vpc_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:vpc/{item['VpcId']}"


def _subnet_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:subnet/{item['SubnetId']}"


def _sg_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:security-group/{item['GroupId']}"


def _vpce_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:vpc-endpoint/{item['VpcEndpointId']}"


def _natgw_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:natgateway/{item['NatGatewayId']}"


def _eip_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:elastic-ip/{item.get('AllocationId', '')}"


def _tgw_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:transit-gateway/{item['TransitGatewayId']}"


def _vpn_arn(region, account, item):
    return f"arn:aws:ec2:{region}:{account}:vpn-connection/{item['VpnConnectionId']}"


def _s3_arn(region, account, item):
    return f"arn:aws:s3:::{item['Name']}"


def _dynamodb_arn(region, account, item):
    return f"arn:aws:dynamodb:{region}:{account}:table/{item}"


def _kinesis_arn(region, account, item):
    return f"arn:aws:kinesis:{region}:{account}:stream/{item}"


def _sqs_arn(region, account, item):
    # QueueUrl: https://sqs.{region}.amazonaws.com/{account}/{name}
    name = item.rsplit("/", 1)[-1]
    return f"arn:aws:sqs:{region}:{account}:{name}"


def _route53_arn(region, account, item):
    zone_id = item["Id"].split("/")[-1]
    return f"arn:aws:route53:::hostedzone/{zone_id}"


def _cf_arn(region, account, item):
    return f"arn:aws:cloudfront::{account}:distribution/{item['Id']}"


def _apigw_rest_arn(region, account, item):
    return f"arn:aws:apigateway:{region}::/restapis/{item['id']}"


def _apigw_http_arn(region, account, item):
    return f"arn:aws:apigateway:{region}::/apis/{item['ApiId']}"


def _opensearch_arn(region, account, item):
    return f"arn:aws:es:{region}:{account}:domain/{item['DomainName']}"


SERVICE_DEFINITIONS = {
    # --- Compute ---
    "EC2 Instances": {
        "client": "ec2",
        "func": "describe_instances",
        "key": lambda r: [i for res in r.get("Reservations", []) for i in res["Instances"]],
        "arn": _ec2_arn,
        "columns": {
            "InstanceId": lambda i: i["InstanceId"],
            "Name": _tag_name,
            "Type": lambda i: i["InstanceType"],
            "State": lambda i: i["State"]["Name"],
            "AZ": lambda i: i["Placement"]["AvailabilityZone"],
        },
    },
    "Lambda Functions": {
        "client": "lambda",
        "func": "list_functions",
        "key": "Functions",
        "arn": "FunctionArn",
        "columns": {
            "FunctionName": "FunctionName",
            "Runtime": "Runtime",
            "Memory(MB)": "MemorySize",
        },
    },
    "ECS Clusters": {
        "client": "ecs",
        "func": "list_clusters",
        "key": "clusterArns",
        "arn": lambda r, a, i: i,  # item自体がARN
        "columns": {"ClusterArn": lambda i: i},
    },
    "Auto Scaling Groups": {
        "client": "autoscaling",
        "func": "describe_auto_scaling_groups",
        "key": "AutoScalingGroups",
        "arn": "AutoScalingGroupARN",
        "columns": {
            "Name": "AutoScalingGroupName",
            "Min": "MinSize",
            "Max": "MaxSize",
            "Desired": "DesiredCapacity",
        },
    },
    "ECR Repositories": {
        "client": "ecr",
        "func": "describe_repositories",
        "key": "repositories",
        "arn": "repositoryArn",
        "columns": {
            "RepositoryName": "repositoryName",
            "URI": "repositoryUri",
            "CreatedAt": lambda i: str(i.get("createdAt", "")),
        },
    },
    # --- Storage ---
    "S3 Buckets": {
        "client": "s3",
        "func": "list_buckets",
        "key": "Buckets",
        "is_global": True,
        "arn": _s3_arn,
        "columns": {
            "BucketName": "Name",
            "CreationDate": lambda i: str(i.get("CreationDate", "")),
        },
    },
    "EBS Volumes": {
        "client": "ec2",
        "func": "describe_volumes",
        "key": "Volumes",
        "arn": _ebs_arn,
        "columns": {
            "VolumeId": "VolumeId",
            "Size(GiB)": "Size",
            "Type": "VolumeType",
            "State": "State",
            "AZ": "AvailabilityZone",
        },
    },
    "EFS File Systems": {
        "client": "efs",
        "func": "describe_file_systems",
        "key": "FileSystems",
        "arn": "FileSystemArn",
        "columns": {
            "FileSystemId": "FileSystemId",
            "Name": lambda i: i.get("Name", ""),
            "LifeCycleState": "LifeCycleState",
        },
    },
    # --- Storage (additional) ---
    "FSx File Systems": {
        "client": "fsx",
        "func": "describe_file_systems",
        "key": "FileSystems",
        "arn": "ResourceARN",
        "columns": {
            "FileSystemId": "FileSystemId",
            "Type": "FileSystemType",
            "StorageCapacity(GiB)": "StorageCapacity",
            "Lifecycle": "Lifecycle",
        },
    },
    "Backup Vaults": {
        "client": "backup",
        "func": "list_backup_vaults",
        "key": "BackupVaultList",
        "arn": "BackupVaultArn",
        "columns": {
            "VaultName": "BackupVaultName",
            "RecoveryPoints": "NumberOfRecoveryPoints",
            "CreatedAt": lambda i: str(i.get("CreationDate", "")),
        },
    },
    # --- Database ---
    "RDS Instances": {
        "client": "rds",
        "func": "describe_db_instances",
        "key": "DBInstances",
        "arn": "DBInstanceArn",
        "columns": {
            "DBInstanceId": "DBInstanceIdentifier",
            "Engine": "Engine",
            "Class": "DBInstanceClass",
            "Status": "DBInstanceStatus",
        },
    },
    "DynamoDB Tables": {
        "client": "dynamodb",
        "func": "list_tables",
        "key": "TableNames",
        "arn": _dynamodb_arn,
        "columns": {"TableName": lambda i: i},
    },
    "ElastiCache Clusters": {
        "client": "elasticache",
        "func": "describe_cache_clusters",
        "key": "CacheClusters",
        "arn": "ARN",
        "columns": {
            "CacheClusterId": "CacheClusterId",
            "Engine": "Engine",
            "NodeType": "CacheNodeType",
            "Status": "CacheClusterStatus",
        },
    },
    "RDS Snapshots (Manual)": {
        "client": "rds",
        "func": "describe_db_snapshots",
        "key": "DBSnapshots",
        "func_kwargs": {"SnapshotType": "manual"},
        "arn": "DBSnapshotArn",
        "columns": {
            "SnapshotId": "DBSnapshotIdentifier",
            "DBInstance": "DBInstanceIdentifier",
            "Engine": "Engine",
            "Size(GiB)": "AllocatedStorage",
            "Status": "Status",
        },
    },
    "Redshift Clusters": {
        "client": "redshift",
        "func": "describe_clusters",
        "key": "Clusters",
        "arn": lambda r, a, i: f"arn:aws:redshift:{r}:{a}:cluster:{i['ClusterIdentifier']}",
        "columns": {
            "ClusterId": "ClusterIdentifier",
            "NodeType": "NodeType",
            "Nodes": "NumberOfNodes",
            "Status": "ClusterStatus",
        },
    },
    "OpenSearch Domains": {
        "client": "opensearch",
        "func": "list_domain_names",
        "key": "DomainNames",
        "arn": _opensearch_arn,
        "columns": {
            "DomainName": "DomainName",
            "EngineType": lambda i: i.get("EngineType", ""),
        },
    },
    # --- Network ---
    "VPCs": {
        "client": "ec2",
        "func": "describe_vpcs",
        "key": "Vpcs",
        "arn": _vpc_arn,
        "columns": {
            "VpcId": "VpcId",
            "Name": _tag_name,
            "CIDR": "CidrBlock",
            "State": "State",
        },
    },
    "Subnets": {
        "client": "ec2",
        "func": "describe_subnets",
        "key": "Subnets",
        "arn": "SubnetArn",
        "columns": {
            "SubnetId": "SubnetId",
            "Name": _tag_name,
            "VpcId": "VpcId",
            "CIDR": "CidrBlock",
            "AZ": "AvailabilityZone",
        },
    },
    "Security Groups": {
        "client": "ec2",
        "func": "describe_security_groups",
        "key": "SecurityGroups",
        "arn": _sg_arn,
        "columns": {
            "GroupId": "GroupId",
            "GroupName": "GroupName",
            "VpcId": "VpcId",
        },
    },
    "VPC Endpoints": {
        "client": "ec2",
        "func": "describe_vpc_endpoints",
        "key": "VpcEndpoints",
        "arn": _vpce_arn,
        "columns": {
            "EndpointId": "VpcEndpointId",
            "VpcId": "VpcId",
            "ServiceName": "ServiceName",
            "Type": "VpcEndpointType",
            "State": lambda i: i.get("State", ""),
        },
    },
    "NAT Gateways": {
        "client": "ec2",
        "func": "describe_nat_gateways",
        "key": "NatGateways",
        "arn": _natgw_arn,
        "columns": {
            "NatGatewayId": "NatGatewayId",
            "Name": _tag_name,
            "VpcId": "VpcId",
            "State": "State",
            "Type": lambda i: i.get("ConnectivityType", ""),
        },
    },
    "Elastic IPs": {
        "client": "ec2",
        "func": "describe_addresses",
        "key": "Addresses",
        "arn": _eip_arn,
        "columns": {
            "PublicIp": "PublicIp",
            "Name": _tag_name,
            "AssociationId": lambda i: i.get("AssociationId", "(未割当)"),
            "InstanceId": lambda i: i.get("InstanceId", ""),
        },
    },
    "Transit Gateways": {
        "client": "ec2",
        "func": "describe_transit_gateways",
        "key": "TransitGateways",
        "arn": "TransitGatewayArn",
        "columns": {
            "TgwId": "TransitGatewayId",
            "Name": _tag_name,
            "State": "State",
        },
    },
    "VPN Connections": {
        "client": "ec2",
        "func": "describe_vpn_connections",
        "key": "VpnConnections",
        "arn": _vpn_arn,
        "columns": {
            "VpnConnectionId": "VpnConnectionId",
            "Name": _tag_name,
            "State": "State",
            "Type": "Type",
        },
    },
    "ELBv2 (ALB/NLB)": {
        "client": "elbv2",
        "func": "describe_load_balancers",
        "key": "LoadBalancers",
        "arn": "LoadBalancerArn",
        "columns": {
            "Name": "LoadBalancerName",
            "Type": "Type",
            "Scheme": "Scheme",
            "State": lambda i: i.get("State", {}).get("Code", ""),
            "DNSName": "DNSName",
        },
    },
    "CloudFront Distributions": {
        "client": "cloudfront",
        "func": "list_distributions",
        "key": lambda r: (r.get("DistributionList") or {}).get("Items") or [],
        "is_global": True,
        "arn": "ARN",
        "columns": {
            "Id": "Id",
            "DomainName": "DomainName",
            "Status": "Status",
        },
    },
    "Route53 Hosted Zones": {
        "client": "route53",
        "func": "list_hosted_zones",
        "key": "HostedZones",
        "is_global": True,
        "arn": _route53_arn,
        "columns": {
            "Id": lambda i: i["Id"].split("/")[-1],
            "Name": "Name",
            "Type": lambda i: "Private" if i.get("Config", {}).get("PrivateZone") else "Public",
        },
    },
    # --- Analytics / Integration ---
    "Kinesis Data Streams": {
        "client": "kinesis",
        "func": "list_streams",
        "key": lambda r: r.get("StreamNames") or [],
        "arn": _kinesis_arn,
        "columns": {"StreamName": lambda i: i},
    },
    "Step Functions": {
        "client": "stepfunctions",
        "func": "list_state_machines",
        "key": "stateMachines",
        "arn": "stateMachineArn",
        "columns": {
            "Name": "name",
            "Type": "type",
        },
    },
    "API Gateway REST APIs": {
        "client": "apigateway",
        "func": "get_rest_apis",
        "key": "items",
        "arn": _apigw_rest_arn,
        "columns": {
            "Name": "name",
            "Id": "id",
            "EndpointType": lambda i: ",".join(i.get("endpointConfiguration", {}).get("types", [])),
        },
    },
    "API Gateway HTTP APIs": {
        "client": "apigatewayv2",
        "func": "get_apis",
        "key": "Items",
        "arn": _apigw_http_arn,
        "columns": {
            "Name": "Name",
            "ApiId": "ApiId",
            "ProtocolType": "ProtocolType",
        },
    },
    # --- Security / IAM ---
    "IAM Users": {
        "client": "iam",
        "func": "list_users",
        "key": "Users",
        "is_global": True,
        "arn": "Arn",
        "columns": {
            "UserName": "UserName",
            "CreateDate": lambda i: str(i.get("CreateDate", "")),
        },
    },
    "IAM Roles": {
        "client": "iam",
        "func": "list_roles",
        "key": "Roles",
        "is_global": True,
        "arn": "Arn",
        "columns": {
            "RoleName": "RoleName",
            "CreateDate": lambda i: str(i.get("CreateDate", "")),
        },
    },
    "KMS Keys": {
        "client": "kms",
        "func": "list_keys",
        "key": "Keys",
        "arn": "KeyArn",
        "post_filter": "kms_customer_keys",
        "columns": {
            "KeyId": "KeyId",
            "KeyManager": lambda i: i.get("_KeyManager", ""),
            "Description": lambda i: i.get("_Description", ""),
        },
    },
    "Secrets Manager": {
        "client": "secretsmanager",
        "func": "list_secrets",
        "key": "SecretList",
        "arn": "ARN",
        "columns": {
            "Name": "Name",
            "LastAccessed": lambda i: str(i.get("LastAccessedDate", "")),
        },
    },
    "WAF Web ACLs": {
        "client": "wafv2",
        "func": "list_web_acls",
        "key": "WebACLs",
        "func_kwargs": {"Scope": "REGIONAL"},
        "arn": "ARN",
        "columns": {
            "Name": "Name",
            "Id": "Id",
        },
    },
    # --- Management ---
    "CloudFormation Stacks": {
        "client": "cloudformation",
        "func": "describe_stacks",
        "key": "Stacks",
        "arn": "StackId",
        "columns": {
            "StackName": "StackName",
            "Status": "StackStatus",
            "CreatedTime": lambda i: str(i.get("CreationTime", "")),
        },
    },
    "SNS Topics": {
        "client": "sns",
        "func": "list_topics",
        "key": "Topics",
        "arn": "TopicArn",
        "columns": {
            "TopicArn": "TopicArn",
        },
    },
    "CloudWatch Alarms": {
        "client": "cloudwatch",
        "func": "describe_alarms",
        "key": lambda r: r.get("MetricAlarms", []) + r.get("CompositeAlarms", []),
        "arn": "AlarmArn",
        "columns": {
            "AlarmName": "AlarmName",
            "State": "StateValue",
            "Namespace": lambda i: i.get("Namespace", "(composite)"),
        },
    },
    "SQS Queues": {
        "client": "sqs",
        "func": "list_queues",
        "key": lambda r: r.get("QueueUrls") or [],
        "arn": _sqs_arn,
        "columns": {
            "QueueUrl": lambda i: i,
        },
    },
}
