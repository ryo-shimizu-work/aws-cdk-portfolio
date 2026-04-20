import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as ecs from "aws-cdk-lib/aws-ecs";

export interface GitHubActionsRoleProps {
  readonly repository: ecr.Repository;
  readonly service: ecs.FargateService;
}

export class GitHubActionsRoleConstruct extends Construct {
  readonly roleArn: string;

  constructor(scope: Construct, id: string, props: GitHubActionsRoleProps) {
    super(scope, id);

    const provider = new iam.OpenIdConnectProvider(this, "GitHubOidcProvider", {
      url: "https://token.actions.githubusercontent.com",
      clientIds: ["sts.amazonaws.com"],
    });

    const role = new iam.Role(this, "GitHubActionsRole", {
      assumedBy: new iam.WebIdentityPrincipal(provider.openIdConnectProviderArn, {
        StringEquals: {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub":
            "repo:<GITHUB_OWNER>/<GITHUB_REPO>:ref:refs/heads/main",
        },
      }),
    });
    this.roleArn = role.roleArn;

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: ["ecr:GetAuthorizationToken"],
        resources: ["*"],
      }),
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "ecr:BatchCheckLayerAvailability",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ],
        resources: [props.repository.repositoryArn],
      }),
    );

    role.addToPolicy(
      new iam.PolicyStatement({
        actions: ["ecs:UpdateService"],
        resources: [props.service.serviceArn],
      }),
    );
  }
}
