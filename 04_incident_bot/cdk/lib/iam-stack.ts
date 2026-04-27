import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';
import { parameter } from '../parameter';

export class IamStack extends cdk.Stack {
  readonly lambdaRole: iam.Role;

  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    this.lambdaRole = new iam.Role(this, 'LambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
      inlinePolicies: {
        IncidentBotPolicy: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'logs:StartQuery',
                'logs:GetQueryResults',
              ],
              resources: [
                `arn:aws:logs:${parameter.region}:${parameter.accountId}:log-group:${parameter.logGroup.name}:*`,
              ],
            }),
            new iam.PolicyStatement({
              actions: ['bedrock:InvokeModel'],
              resources: [
                `arn:aws:bedrock:${parameter.region}::foundation-model/${parameter.bedrock.modelId}`,
              ],
            }),
          ],
        }),
      },
    });
  }
}
