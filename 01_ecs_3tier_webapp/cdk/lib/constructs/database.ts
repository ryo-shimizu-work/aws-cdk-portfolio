import { Duration, RemovalPolicy } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as rds from "aws-cdk-lib/aws-rds";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";

export interface DatabaseProps {
  readonly envName: string;
  readonly vpc: ec2.Vpc;
  readonly rdsSg: ec2.SecurityGroup;
}

/**
 * Aurora PostgreSQL Serverless v2 + Secrets Manager を管理する Construct。
 *
 * Serverless v2 を選んだ理由:
 *   - 学習用途でコストを最小化しつつ、本番昇格を見据えた設計が可能
 *   - プロビジョンド Aurora と同じ API で操作できるため移行コストが低い
 *
 * 却下した代替案:
 *   - RDS PostgreSQL (Single-AZ): フェイルオーバー体験が得られない
 *   - DynamoDB: リレーショナルモデルの学習目的に不適
 */
export class DatabaseConstruct extends Construct {
  readonly cluster: rds.DatabaseCluster;
  readonly secret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props: DatabaseProps) {
    super(scope, id);

    // DB 認証情報を Secrets Manager で自動生成・ローテーション対象にする
    const dbSecret = new secretsmanager.Secret(this, "DbSecret", {
      secretName: `/${props.envName}/db/credentials`,
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: "appuser" }),
        generateStringKey: "password",
        excludePunctuation: true,
        includeSpace: false,
      },
    });

    const subnetGroup = new rds.SubnetGroup(this, "SubnetGroup", {
      vpc: props.vpc,
      description: "Aurora isolated subnet group",
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      removalPolicy: RemovalPolicy.DESTROY, // 学習用のみ。本番は RETAIN
    });

    // Aurora Serverless v2: minCapacity=0.5 ACU でほぼ停止状態をキープ
    // 本番では min=2 以上にしてコールドスタートを排除する
    this.cluster = new rds.DatabaseCluster(this, "AuroraCluster", {
      clusterIdentifier: `${props.envName}-aurora`,
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_16_6,
      }),
      credentials: rds.Credentials.fromSecret(dbSecret),
      serverlessV2MinCapacity: 0.5,
      serverlessV2MaxCapacity: 4,
      writer: rds.ClusterInstance.serverlessV2("Writer"),
      // 学習用に Reader は省略。本番では追加してフェイルオーバーを検証する
      vpc: props.vpc,
      securityGroups: [props.rdsSg],
      subnetGroup,
      defaultDatabaseName: "appdb",
      storageEncrypted: true,
      backup: {
        retention: Duration.days(7),
        preferredWindow: "02:00-03:00",
      },
      removalPolicy: RemovalPolicy.DESTROY, // 学習用のみ。本番は RETAIN
    });

    this.secret = dbSecret;
  }
}
