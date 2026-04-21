import { RemovalPolicy } from "aws-cdk-lib";
import { Construct } from "constructs";
import * as ecr from "aws-cdk-lib/aws-ecr";

export interface EcrProps {
  readonly envName: string;
  readonly ecrRepositoryName: string;
}

export class EcrConstruct extends Construct {
  readonly repository: ecr.Repository;

  constructor(scope: Construct, id: string, props: EcrProps) {
    super(scope, id);

    this.repository = new ecr.Repository(this, "Repository", {
      repositoryName: props.ecrRepositoryName,
      imageScanOnPush: true,
      lifecycleRules: [
        {
          maxImageCount: 10,
          rulePriority: 1,
          description: "keep last 10 images",
        },
      ],
      removalPolicy: RemovalPolicy.DESTROY,
    });
  }
}
