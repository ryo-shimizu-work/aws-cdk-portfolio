import { Duration, RemovalPolicy } from "aws-cdk-lib";
import * as path from "path";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53targets from "aws-cdk-lib/aws-route53-targets";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as synthetics from "aws-cdk-lib/aws-synthetics";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as ecr from "aws-cdk-lib/aws-ecr";

export interface ComputeProps {
  readonly envName: string;
  readonly vpc: ec2.Vpc;
  readonly albSg: ec2.SecurityGroup;
  readonly ecsSg: ec2.SecurityGroup;
  readonly dbSecret: secretsmanager.ISecret;
  // DB 接続先ホスト (DatabaseConstruct.cluster.clusterEndpoint.hostname)
  readonly dbHost: string;
  readonly hostedZone: string;
  readonly domainName: string;
  readonly ecrUri: string;
}

/**
 * ALB + ECS Fargate (Service / Task) を管理する Construct。
 *
 * コンテナイメージ: nginxdemos/hello を使用 (アプリ実装不要で動作確認できる)
 * 本番に置き換える場合は containerImage を ECR イメージに差し替えるだけでよい。
 *
 * ヘルスチェック設計:
 *   ALB ヘルスチェック → /health (200 を期待)
 *   ECS コンテナヘルスチェック → curl で同一エンドポイントを叩く
 *   両方揃えることで「ALBが外してからタスク再起動」の流れを学べる
 */
export class ComputeConstruct extends Construct {
  readonly service: ecs.FargateService;
  readonly alb: elbv2.ApplicationLoadBalancer;

  constructor(scope: Construct, id: string, props: ComputeProps) {
    super(scope, id);

    // ECS Cluster
    const cluster = new ecs.Cluster(this, "Cluster", {
      clusterName: `${props.envName}-cluster`,
      vpc: props.vpc,
      containerInsights: true, // CloudWatch Container Insights 有効
    });

    // Task 実行ロール: ECR pull + Secrets Manager 読み取りに必要
    const executionRole = new iam.Role(this, "TaskExecutionRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AmazonECSTaskExecutionRolePolicy",
        ),
      ],
    });
    // Secrets Manager から DB 認証情報を取得する権限
    props.dbSecret.grantRead(executionRole);

    // Task ロール: アプリコードが AWS API を呼ぶ場合はここに追加
    const taskRole = new iam.Role(this, "TaskRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    });

    const logGroup = new logs.LogGroup(this, "AppLogGroup", {
      logGroupName: `/ecs/${props.envName}/app`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const taskDef = new ecs.FargateTaskDefinition(this, "TaskDef", {
      cpu: 256,
      memoryLimitMiB: 512,
      executionRole,
      taskRole,
    });

    taskDef.addContainer("AppContainer", {
      // プライベート ECR（:latest）からイメージを取得する
      image: ecs.ContainerImage.fromEcrRepository(
        ecr.Repository.fromRepositoryName(this, 'AppRepo', props.ecrUri.split('/').slice(-1)[0]),
        'latest',
      ),
      portMappings: [{ containerPort: 80 }],
      environment: {
        DB_HOST: props.dbHost,
        ENV_NAME: props.envName,
      },
      secrets: {
        // Secrets Manager の値をコンテナ環境変数に注入
        DB_USERNAME: ecs.Secret.fromSecretsManager(props.dbSecret, "username"),
        DB_PASSWORD: ecs.Secret.fromSecretsManager(props.dbSecret, "password"),
      },
      logging: ecs.LogDrivers.awsLogs({
        logGroup,
        streamPrefix: "app",
      }),
      healthCheck: {
        command: ["CMD-SHELL", "curl -f http://localhost/ || exit 1"],
        interval: Duration.seconds(30),
        timeout: Duration.seconds(5),
        retries: 3,
        startPeriod: Duration.seconds(60),
      },
    });

    // ALB (Internet-facing, Public Subnet)
    this.alb = new elbv2.ApplicationLoadBalancer(this, "Alb", {
      loadBalancerName: `${props.envName}-alb`,
      vpc: props.vpc,
      internetFacing: true,
      securityGroup: props.albSg,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
    });

    // Route53
    const hostedZone = route53.HostedZone.fromLookup(this, "HostedZone", {
      domainName: props.hostedZone,
    });

    // ACM
    const certificate = new acm.Certificate(this, "Certificate", {
      domainName: `${props.domainName}.${props.hostedZone}`,
      validation: acm.CertificateValidation.fromDns(hostedZone),
    });

    const listener = this.alb.addListener("HttpsListener", {
      port: 443,
      open: false,
      certificates: [
        elbv2.ListenerCertificate.fromArn(certificate.certificateArn),
      ],
    });

    this.alb.addListener("HttpListener", {
      port: 80,
      open: false,
      defaultAction: elbv2.ListenerAction.redirect({
        protocol: "HTTPS",
        port: "443",
        permanent: true,
      }),
    });

    new route53.ARecord(this, "AliasRecord", {
      zone: hostedZone,
      recordName: props.domainName,
      target: route53.RecordTarget.fromAlias(
        new route53targets.LoadBalancerTarget(this.alb, {
          evaluateTargetHealth: true,
        }),
      ),
    });

    // ECS Fargate Service
    this.service = new ecs.FargateService(this, "Service", {
      serviceName: `${props.envName}-service`,
      cluster,
      taskDefinition: taskDef,
      desiredCount: 0, // 0にしておかないと初回デプロイ時、ECRイメージがpushされていないため、デプロイに失敗する。
      securityGroups: [props.ecsSg],
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      // デプロイ失敗時に自動ロールバックするサーキットブレーカー
      circuitBreaker: { rollback: true },
      enableExecuteCommand: true, // ECS Exec でコンテナにログインできるようにする
    });

    listener.addTargets("EcsTarget", {
      // targetGroupName: `${props.envName}-tg`, // 固定名を使うと名前衝突の可能性があるため削除
      targets: [this.service],
      protocol: elbv2.ApplicationProtocol.HTTP,
      port: 80,
      healthCheck: {
        path: "/",
        interval: Duration.seconds(30),
        healthyHttpCodes: "200",
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 3,
      },
      deregistrationDelay: Duration.seconds(30),
    });

    // canary
    const canaryBucket = new s3.Bucket(this, 'CanaryBucket', {
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    new synthetics.Canary(this, 'EcsCanary', {
      artifactsBucketLocation: { bucket: canaryBucket },
      schedule: synthetics.Schedule.rate(Duration.minutes(5)),
      test: synthetics.Test.custom({
        code: synthetics.Code.fromAsset(path.join(__dirname, 'canary')),
        handler: 'index.handler',
      }),
      runtime: synthetics.Runtime.SYNTHETICS_NODEJS_PUPPETEER_9_1,
      environmentVariables: {
        TARGET_URL: `https://${props.domainName}.${props.hostedZone}`,
      },
    });
  }
}
