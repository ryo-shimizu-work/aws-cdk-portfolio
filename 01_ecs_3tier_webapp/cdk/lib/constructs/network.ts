import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";

export interface NetworkProps {
  readonly envName: string;
  readonly allowedCidr: string[];
}

/**
 * VPC / Subnet / Security Group を管理する Construct。
 *
 * サブネット設計:
 *   Public    → ALB (インターネット向けロードバランサー)
 *   Private   → ECS Fargate タスク (アウトバウンドは NAT GW 経由)
 *   Isolated  → Aurora (インターネット到達性なし)
 *
 * SG の原則: 最小権限。SG 参照で IP レンジを使わない。
 */
export class NetworkConstruct extends Construct {
  readonly vpc: ec2.Vpc;
  readonly albSg: ec2.SecurityGroup;
  readonly ecsSg: ec2.SecurityGroup;
  readonly rdsSg: ec2.SecurityGroup;
  readonly vpcEndpointSg: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: NetworkProps) {
    super(scope, id);

    // VPC: 2 AZ, NAT GW は 1 つ (コスト優先; 本番は AZ 数分に増やす)
    this.vpc = new ec2.Vpc(this, "Vpc", {
      vpcName: `${props.envName}-vpc`,
      maxAzs: 2,
      natGateways: 0, //L2コンストラクタなので、0を指定せずに削除するとPublicサブネットに勝手に作成される。
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "Public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: "Private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
        {
          cidrMask: 24,
          name: "Isolated",
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    // ALB SG: インターネット → 443 (80 は ALB レベルでリダイレクト)
    this.albSg = new ec2.SecurityGroup(this, "AlbSg", {
      vpc: this.vpc,
      securityGroupName: `${props.envName}-alb-sg`,
      description: "ALB: allow HTTPS from internet",
    });
    props.allowedCidr.forEach((cidr) => {
      this.albSg.addIngressRule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(443));
      this.albSg.addIngressRule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(80));
    });

    // ECS SG: ALB SG からのみ受け付ける (IP レンジ指定なし)
    this.ecsSg = new ec2.SecurityGroup(this, "EcsSg", {
      vpc: this.vpc,
      securityGroupName: `${props.envName}-ecs-sg`,
      description: "ECS Fargate: allow traffic from ALB",
    });
    this.ecsSg.addIngressRule(
      ec2.Peer.securityGroupId(this.albSg.securityGroupId),
      // ec2.Port.tcp(8080), コンテナのポートマッピングが80で受け付けているため削除
      ec2.Port.tcp(80),
      "from ALB",
    );

    // RDS SG: ECS SG からのみ受け付ける
    this.rdsSg = new ec2.SecurityGroup(this, "RdsSg", {
      vpc: this.vpc,
      securityGroupName: `${props.envName}-rds-sg`,
      description: "Aurora: allow traffic from ECS",
    });
    this.rdsSg.addIngressRule(
      ec2.Peer.securityGroupId(this.ecsSg.securityGroupId),
      ec2.Port.tcp(5432),
      "from ECS",
    );

    // Endpoint SG: ecr SG からのみ受け付ける
    this.vpcEndpointSg = new ec2.SecurityGroup(this, "EndpointSg", {
      vpc: this.vpc,
      securityGroupName: `${props.envName}-endpoint-sg`,
      description: "Endpoint: allow HTTPS traffic from ECS",
    });
    this.vpcEndpointSg.addIngressRule(
      ec2.Peer.securityGroupId(this.ecsSg.securityGroupId),
      ec2.Port.tcp(443),
      "from ECS",
    );

    const endpointServices = [
      ec2.InterfaceVpcEndpointAwsService.ECR,
      ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
      ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
      ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
    ];
    endpointServices.forEach((service) => {
      this.vpc.addInterfaceEndpoint(service.shortName, {
        service,
        subnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        securityGroups: [this.vpcEndpointSg],
      });
    });

    this.vpc.addGatewayEndpoint("S3Endpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });
  }
}
