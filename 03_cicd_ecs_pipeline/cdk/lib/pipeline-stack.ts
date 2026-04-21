import { Stack, StackProps, CfnOutput } from "aws-cdk-lib";
import { Construct } from "constructs";
import { NetworkConstruct } from "./constructs/network";
import { EcrConstruct } from "./constructs/ecr";
import { ComputeConstruct } from "./constructs/compute";
import { PipelineConstruct } from "./constructs/pipeline";
import * as iam from "aws-cdk-lib/aws-iam";

export interface PipelineStackProps extends StackProps {
  readonly envName: string;
  readonly accountId: string;
  readonly region: string;
  readonly allowedCidr: string[];
  readonly ecrRepositoryName: string;
  readonly githubRepo: string;
}

/**
 * CI/CD パイプライン v2.0 のルートスタック。
 *
 * Construct 間の依存関係:
 *   NetworkConstruct → EcrConstruct → ComputeConstruct → PipelineConstruct
 */
export class PipelineStack extends Stack {
  constructor(scope: Construct, id: string, props: PipelineStackProps) {
    super(scope, id, props);

    const network = new NetworkConstruct(this, "Network", {
      envName: props.envName,
      allowedCidr: props.allowedCidr,
    });

    const ecr = new EcrConstruct(this, "Ecr", {
      envName: props.envName,
      ecrRepositoryName: props.ecrRepositoryName,
    });

    const compute = new ComputeConstruct(this, "Compute", {
      envName: props.envName,
      vpc: network.vpc,
      albSg: network.albSg,
      ecsSg: network.ecsSg,
      repository: ecr.repository,
    });

    new PipelineConstruct(this, "Pipeline", {
      envName: props.envName,
      service: compute.service,
      repository: ecr.repository,
      blueTargetGroup: compute.blueTargetGroup,
      greenTargetGroup: compute.greenTargetGroup,
      productionListener: compute.productionListener,
      testListener: compute.testListener,
      taskDefinitionFamily: `${props.envName}-pipeline-task`,
      containerName: "app",
    });

    // GitHub Actions v2.0 用 OIDC ロール
    const provider = new iam.OpenIdConnectProvider(this, "GitHubOidcProvider", {
      url: "https://token.actions.githubusercontent.com",
      clientIds: ["sts.amazonaws.com"],
    });

    const githubRole = new iam.Role(this, "GitHubActionsRole", {
      assumedBy: new iam.WebIdentityPrincipal(provider.openIdConnectProviderArn, {
        StringEquals: {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub":
            `repo:${props.githubRepo}:ref:refs/heads/main`,
        },
      }),
    });

    githubRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["ecr:GetAuthorizationToken"],
        resources: ["*"],
      }),
    );

    githubRole.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ],
        resources: [ecr.repository.repositoryArn],
      }),
    );

    new CfnOutput(this, "GitHubActionsRoleArn", {
      value: githubRole.roleArn,
      description: "GitHub Actions OIDC Role ARN (v2)",
    });

    new CfnOutput(this, "AlbDnsName", {
      value: compute.alb.loadBalancerDnsName,
      description: "ALB DNS Name (production :80)",
    });

    new CfnOutput(this, "AlbTestDnsName", {
      value: `${compute.alb.loadBalancerDnsName}:8080`,
      description: "ALB DNS Name (test :8080)",
    });

    new CfnOutput(this, "EcrRepositoryUri", {
      value: ecr.repository.repositoryUri,
      description: "ECR Repository URI",
    });
  }
}
