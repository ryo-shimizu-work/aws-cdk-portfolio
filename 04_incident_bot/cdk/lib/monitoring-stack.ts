import * as cdk from 'aws-cdk-lib';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import { Construct } from 'constructs';
import { parameter } from '../parameter';

export class MonitoringStack extends cdk.Stack {
  readonly alarmArn: string;

  constructor(scope: Construct, id: string, props: cdk.StackProps) {
    super(scope, id, props);

    const logGroup = new logs.LogGroup(this, 'AppLogGroup', {
      logGroupName: parameter.logGroup.name,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const metricFilter = new logs.MetricFilter(this, 'ErrorMetricFilter', {
      logGroup,
      metricNamespace: 'IncidentBot',
      metricName: 'ErrorCount',
      filterPattern: logs.FilterPattern.literal('ERROR'),
      metricValue: '1',
      defaultValue: 0,
    });

    const errorMetric = metricFilter.metric({
      statistic: 'Sum',
      period: cdk.Duration.minutes(1),
    });

    const alarm = new cloudwatch.Alarm(this, 'ErrorAlarm', {
      alarmName: 'incident-bot-error-alarm',
      metric: errorMetric,
      threshold: 1,
      evaluationPeriods: 1,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    this.alarmArn = alarm.alarmArn;

    new cdk.CfnOutput(this, 'AlarmArn', { value: alarm.alarmArn });
  }
}
