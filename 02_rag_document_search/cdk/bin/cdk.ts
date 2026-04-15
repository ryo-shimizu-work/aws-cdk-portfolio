#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { DatasourceStack } from '../lib/datasource-stack';
import { IamStack } from '../lib/iam-stack';
import { OpenSearchStack } from '../lib/opensearch-stack';
import { KnowledgeBaseStack } from '../lib/knowledge-base-stack';
import { ComputeStack } from '../lib/compute-stack';
import { parameter } from "../parameter";

const app = new cdk.App();

const env = {
  account: parameter.accountId,
  region: parameter.region,
};

const datasourceStack = new DatasourceStack(app, 'DatasourceStack', { env });

const iamStack = new IamStack(app, 'IamStack', {
  env,
  documentBucket: datasourceStack.bucket,
});
iamStack.addDependency(datasourceStack);

const openSearchStack = new OpenSearchStack(app, 'OpenSearchStack', {
  env,
  knowledgeBaseRole: iamStack.knowledgeBaseRole,
});
openSearchStack.addDependency(iamStack);

const knowledgeBaseStack = new KnowledgeBaseStack(app, 'KnowledgeBaseStack', {
  env,
  documentBucket: datasourceStack.bucket,
  collectionArn: openSearchStack.collectionArn,
  knowledgeBaseRole: iamStack.knowledgeBaseRole,
});
knowledgeBaseStack.addDependency(openSearchStack);

const computeStack = new ComputeStack(app, 'ComputeStack', {
  env,
  knowledgeBaseId: knowledgeBaseStack.knowledgeBaseId,
  knowledgeBaseArn: knowledgeBaseStack.knowledgeBaseArn,
});
computeStack.addDependency(knowledgeBaseStack);
