import { Duration, RemovalPolicy } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as ecr from "aws-cdk-lib/aws-ecr";

export interface ComputeProps {
  readonly envName: string;
  readonly vpc: ec2.Vpc;
  readonly albSg: ec2.SecurityGroup;
  readonly ecsSg: ec2.SecurityGroup;
  readonly repository: ecr.Repository;
}

export class ComputeConstruct extends Construct {
  readonly service: ecs.FargateService;
  readonly alb: elbv2.ApplicationLoadBalancer;
  readonly blueTargetGroup: elbv2.ApplicationTargetGroup;
  readonly greenTargetGroup: elbv2.ApplicationTargetGroup;
  readonly productionListener: elbv2.ApplicationListener;
  readonly testListener: elbv2.ApplicationListener;

  constructor(scope: Construct, id: string, props: ComputeProps) {
    super(scope, id);

    const cluster = new ecs.Cluster(this, "Cluster", {
      clusterName: `${props.envName}-pipeline-cluster`,
      vpc: props.vpc,
    });

    const executionRole = new iam.Role(this, "TaskExecutionRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AmazonECSTaskExecutionRolePolicy",
        ),
      ],
    });

    const logGroup = new logs.LogGroup(this, "AppLogGroup", {
      logGroupName: `/ecs/${props.envName}/pipeline-app`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const taskDef = new ecs.FargateTaskDefinition(this, "TaskDef", {
      family: `${props.envName}-pipeline-task`,
      cpu: 256,
      memoryLimitMiB: 512,
      executionRole,
    });

    taskDef.addContainer("AppContainer", {
      containerName: "app",
      image: ecs.ContainerImage.fromEcrRepository(props.repository, "latest"),
      portMappings: [{ containerPort: 80 }],
      logging: ecs.LogDrivers.awsLogs({ logGroup, streamPrefix: "app" }),
    });

    this.alb = new elbv2.ApplicationLoadBalancer(this, "Alb", {
      loadBalancerName: `${props.envName}-pipeline-alb`,
      vpc: props.vpc,
      internetFacing: true,
      securityGroup: props.albSg,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    // Blue TG（本番トラフィック）
    this.blueTargetGroup = new elbv2.ApplicationTargetGroup(this, "BlueTg", {
      targetGroupName: `${props.envName}-blue-tg`,
      vpc: props.vpc,
      protocol: elbv2.ApplicationProtocol.HTTP,
      port: 80,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: "/",
        interval: Duration.seconds(30),
        healthyHttpCodes: "200",
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      deregistrationDelay: Duration.seconds(30),
    });

    // Green TG（テストトラフィック）
    this.greenTargetGroup = new elbv2.ApplicationTargetGroup(this, "GreenTg", {
      targetGroupName: `${props.envName}-green-tg`,
      vpc: props.vpc,
      protocol: elbv2.ApplicationProtocol.HTTP,
      port: 80,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        path: "/",
        interval: Duration.seconds(30),
        healthyHttpCodes: "200",
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      deregistrationDelay: Duration.seconds(30),
    });

    // 本番リスナー（80）→ Blue TG
    this.productionListener = this.alb.addListener("ProductionListener", {
      port: 80,
      open: false,
      defaultTargetGroups: [this.blueTargetGroup],
    });

    // テストリスナー（8080）→ Green TG
    this.testListener = this.alb.addListener("TestListener", {
      port: 8080,
      open: false,
      defaultTargetGroups: [this.greenTargetGroup],
    });

    // ECS Service: Blue/Green コントローラー
    this.service = new ecs.FargateService(this, "Service", {
      serviceName: `${props.envName}-pipeline-service`,
      cluster,
      taskDefinition: taskDef,
      desiredCount: 0, // 初期は0で起動
      minHealthyPercent: 100,
      securityGroups: [props.ecsSg],
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      deploymentController: { type: ecs.DeploymentControllerType.CODE_DEPLOY },
    });

    // Blue TG にサービスを紐付け（初期状態）
    this.service.attachToApplicationTargetGroup(this.blueTargetGroup);
  }
}
