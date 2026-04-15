import * as cdk from 'aws-cdk-lib/core';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { parameter } from '../parameter';

const EMBEDDING_MODEL_ARN = parameter.models.embedding;

interface IamStackProps extends cdk.StackProps {
  documentBucket: s3.Bucket;
}

export class IamStack extends cdk.Stack {
  public readonly knowledgeBaseRole: iam.Role;

  constructor(scope: Construct, id: string, props: IamStackProps) {
    super(scope, id, props);

    this.knowledgeBaseRole = new iam.Role(this, 'KnowledgeBaseRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      inlinePolicies: {
        KnowledgeBasePolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['s3:GetObject', 's3:ListBucket'],
              resources: [props.documentBucket.bucketArn, `${props.documentBucket.bucketArn}/*`],
            }),
            new iam.PolicyStatement({
              actions: ['bedrock:InvokeModel'],
              resources: [EMBEDDING_MODEL_ARN],
            }),
            new iam.PolicyStatement({
              actions: ['aoss:APIAccessAll'],
              resources: ['*'],
            }),
          ],
        }),
      },
    });
  }
}
