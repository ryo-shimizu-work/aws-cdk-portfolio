import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";

export interface NetworkProps {
  readonly envName: string;
  readonly allowedCidr: string[];
}

export class NetworkConstruct extends Construct {
  readonly vpc: ec2.Vpc;
  readonly albSg: ec2.SecurityGroup;
  readonly ecsSg: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props: NetworkProps) {
    super(scope, id);

    this.vpc = new ec2.Vpc(this, "Vpc", {
      vpcName: `${props.envName}-pipeline-vpc`,
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        { cidrMask: 24, name: "Public", subnetType: ec2.SubnetType.PUBLIC },
        { cidrMask: 24, name: "Private", subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      ],
    });

    this.albSg = new ec2.SecurityGroup(this, "AlbSg", {
      vpc: this.vpc,
      securityGroupName: `${props.envName}-pipeline-alb-sg`,
      description: "ALB: allow HTTP/8080 from allowed CIDR",
    });
    props.allowedCidr.forEach((cidr) => {
      this.albSg.addIngressRule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(80));
      // Blue/Green テストリスナー
      this.albSg.addIngressRule(ec2.Peer.ipv4(cidr), ec2.Port.tcp(8080));
    });

    this.ecsSg = new ec2.SecurityGroup(this, "EcsSg", {
      vpc: this.vpc,
      securityGroupName: `${props.envName}-pipeline-ecs-sg`,
      description: "ECS Fargate: allow traffic from ALB",
    });
    this.ecsSg.addIngressRule(
      ec2.Peer.securityGroupId(this.albSg.securityGroupId),
      ec2.Port.tcp(80),
      "from ALB",
    );
  }
}
