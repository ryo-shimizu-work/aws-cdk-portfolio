#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { IamStack } from '../lib/iam-stack';
import { MonitoringStack } from '../lib/monitoring-stack';
import { ComputeStack } from '../lib/compute-stack';
import { parameter } from '../parameter';

const app = new cdk.App();

const env = {
  account: parameter.accountId,
  region: parameter.region,
};

const iamStack = new IamStack(app, 'IamStack', { env });

const monitoringStack = new MonitoringStack(app, 'MonitoringStack', { env });
monitoringStack.addDependency(iamStack);

const computeStack = new ComputeStack(app, 'ComputeStack', {
  env,
  lambdaRole: iamStack.lambdaRole,
  alarmArn: monitoringStack.alarmArn,
});
computeStack.addDependency(monitoringStack);
