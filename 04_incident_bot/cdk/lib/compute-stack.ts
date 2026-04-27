import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as path from 'path';
import { Construct } from 'constructs';
import { parameter } from '../parameter';

export interface ComputeStackProps extends cdk.StackProps {
  readonly lambdaRole: iam.Role;
  readonly alarmArn: string;
}

export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    const fn = new lambda.Function(this, 'IncidentBotFunction', {
      functionName: 'incident-bot',
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda')),
      role: props.lambdaRole,
      timeout: cdk.Duration.seconds(60),
      environment: {
        SLACK_WEBHOOK_URL: parameter.slack.webhookUrl,
        BEDROCK_MODEL_ID: parameter.bedrock.modelId,
        LOG_GROUP_NAME: parameter.logGroup.name,
        LOOKBACK_MINUTES: String(parameter.logGroup.lookbackMinutes),
      },
    });

    // EventBridge ルール: CloudWatch Alarm の状態変化（ALARM）を検知
    const rule = new events.Rule(this, 'AlarmRule', {
      ruleName: 'incident-bot-alarm-rule',
      eventPattern: {
        source: ['aws.cloudwatch'],
        detailType: ['CloudWatch Alarm State Change'],
        detail: {
          alarmName: ['incident-bot-error-alarm'],
          state: { value: ['ALARM'] },
        },
      },
    });

    rule.addTarget(new targets.LambdaFunction(fn));
  }
}
