import { Stack, StackProps, CfnOutput } from "aws-cdk-lib";
import { Construct } from "constructs";
import { NetworkConstruct } from "./constructs/network";
import { DatabaseConstruct } from "./constructs/database";
import { ComputeConstruct } from "./constructs/compute";
import { EcrConstruct } from "./constructs/ecr";

export interface AppStackProps extends StackProps {
  readonly envName: string;
  readonly accountId: string;
  readonly region: string;
  /** サンプルアプリへのアクセスを許可するCIDR */
  readonly allowedCidr: string[];
  /** Route53で作成済のホストゾーン名 */
  readonly hostedZone: string;
  /** 設定するドメイン名（サブドメインのみ） */
  readonly domainName: string;
  /** パブリックECRのリポジトリ名 */
  readonly ecrRepositoryName: string;
}

/**
 * 3層 Web アプリのルートスタック。
 *
 * Construct 間の依存関係:
 *   NetworkConstruct → DatabaseConstruct → ComputeConstruct
 *
 * props 渡しで参照を管理するため CfnOutput / Fn::ImportValue は不使用。
 * スタック境界がないので循環依存も発生しない。
 */
export class AppStack extends Stack {
  constructor(scope: Construct, id: string, props: AppStackProps) {
    super(scope, id, props);

    const network = new NetworkConstruct(this, "Network", {
      envName: props.envName,
      allowedCidr: props.allowedCidr,
    });

    const database = new DatabaseConstruct(this, "Database", {
      envName: props.envName,
      vpc: network.vpc,
      rdsSg: network.rdsSg,
    });

    // 本ソースコードではECR Public Galleryからイメージを取得しているため、実質的には使用していない。
    // learning/03_cicd_ecs_pipeline の実装に入った時に転用するため作成。
    const ecr = new EcrConstruct(this, "Ecr", {
      envName: props.envName,
      ecrRepositoryName: props.ecrRepositoryName,
    });

    const compute = new ComputeConstruct(this, "Compute", {
      envName: props.envName,
      vpc: network.vpc,
      albSg: network.albSg,
      ecsSg: network.ecsSg,
      dbSecret: database.secret,
      dbHost: database.cluster.clusterEndpoint.hostname,
      hostedZone: props.hostedZone,
      domainName: props.domainName,
      ecrUri: ecr.repository.repositoryUri,
    });

    // デプロイ後に確認する URL
    new CfnOutput(this, "DnsName", {
      value: `https://${props.domainName}.${props.hostedZone}`,
      description: "DNS Name",
    });
  }
}
