import { Stack, StackProps, CfnOutput } from "aws-cdk-lib";
import { Construct } from "constructs";
import { NetworkConstruct } from "./constructs/network";
import { DatabaseConstruct } from "./constructs/database";
import { ComputeConstruct } from "./constructs/compute";

export interface AppStackProps extends StackProps {
  readonly envName: string;
  readonly accontId: string;
  readonly region: string;
  /** サンプルアプリへのアクセスを許可するCIDR */
  allowedCidr: string[];
  hostedZone: string;
  domainName: string;
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

    const compute = new ComputeConstruct(this, "Compute", {
      envName: props.envName,
      vpc: network.vpc,
      albSg: network.albSg,
      ecsSg: network.ecsSg,
      dbSecret: database.secret,
      dbHost: database.cluster.clusterEndpoint.hostname,
      hostedZone: props.hostedZone,
      domainName: props.domainName
    });

    // デプロイ後に確認する URL
    new CfnOutput(this, "DnsName", {
      value: `http://${props.domainName}.${props.hostedZone}`,
      description: "DNS Name",
    });
  }
}
