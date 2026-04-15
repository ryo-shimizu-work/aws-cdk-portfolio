import * as cdk from 'aws-cdk-lib/core';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import { Construct } from 'constructs';
import * as path from 'path';

export const VECTOR_INDEX_NAME = 'rag-index';
export const VECTOR_FIELD_NAME = 'embedding';
export const TEXT_FIELD_NAME = 'text';
export const METADATA_FIELD_NAME = 'metadata';

interface OpenSearchStackProps extends cdk.StackProps {
  knowledgeBaseRole: iam.Role;
}

export class OpenSearchStack extends cdk.Stack {
  public readonly collectionArn: string;
  public readonly collectionEndpoint: string;

  constructor(scope: Construct, id: string, props: OpenSearchStackProps) {
    super(scope, id, props);

    const collectionName = 'rag-collection';

    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'EncryptionPolicy', {
      name: 'rag-encryption-policy',
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [{ ResourceType: 'collection', Resource: [`collection/${collectionName}`] }],
        AWSOwnedKey: true,
      }),
    });

    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'NetworkPolicy', {
      name: 'rag-network-policy',
      type: 'network',
      policy: JSON.stringify([
        {
          Rules: [
            { ResourceType: 'collection', Resource: [`collection/${collectionName}`] },
            { ResourceType: 'dashboard', Resource: [`collection/${collectionName}`] },
          ],
          AllowFromPublic: true,
        },
      ]),
    });

    const collection = new opensearchserverless.CfnCollection(this, 'Collection', {
      name: collectionName,
      type: 'VECTORSEARCH',
    });
    collection.addDependency(encryptionPolicy);
    collection.addDependency(networkPolicy);

    // Custom Resource Lambda の実行ロール
    const indexCreatorRole = new iam.Role(this, 'IndexCreatorRole', {
      roleName: 'rag-index-creator-role',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
      inlinePolicies: {
        OpenSearchAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['aoss:APIAccessAll', 'aoss:DashboardsAccessAll'],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    // DataAccessPolicy: KnowledgeBaseロール + IndexCreatorロール の両方に付与
    // JSON.stringifyはCFnトークンを解決できないためcdk.Fn.subで組み立てる
    const dataAccessPolicy = cdk.Fn.sub(
      JSON.stringify([
        {
          Rules: [
            {
              ResourceType: 'index',
              Resource: [`index/${collectionName}/*`],
              Permission: ['aoss:CreateIndex', 'aoss:WriteDocument', 'aoss:ReadDocument', 'aoss:UpdateIndex', 'aoss:DescribeIndex', 'aoss:DeleteIndex'],
            },
          ],
          Principal: ['${KnowledgeBaseRoleArn}', '${IndexCreatorRoleArn}'],
        },
      ]),
      {
        KnowledgeBaseRoleArn: props.knowledgeBaseRole.roleArn,
        IndexCreatorRoleArn: indexCreatorRole.roleArn,
      }
    );

    const cfnDataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'DataAccessPolicy', {
      name: 'rag-data-access-policy',
      type: 'data',
      policy: dataAccessPolicy,
    });

    // インデックス作成 Custom Resource Lambda
    const requestsLayer = new lambda.LayerVersion(this, 'RequestsLayer', {
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda-layer')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
    });

    const indexCreatorFn = new lambda.Function(this, 'IndexCreatorFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      role: indexCreatorRole,
      timeout: cdk.Duration.minutes(5),
      layers: [requestsLayer],
      code: lambda.Code.fromInline(`
import boto3
import json
import os
import time
import requests
from requests_aws4auth import AWS4Auth

def handler(event, context):
    endpoint = os.environ['COLLECTION_ENDPOINT']
    index = os.environ['INDEX_NAME']
    region = os.environ['REGION']
    request_type = event['RequestType']
    url = f'{endpoint}/{index}'

    session = boto3.Session()
    creds = session.get_credentials()
    auth = AWS4Auth(creds.access_key, creds.secret_key, region, 'aoss', session_token=creds.token)

    if request_type == 'Create':
        body = {
            'settings': {'index': {'knn': True}},
            'mappings': {
                'properties': {
                    os.environ['VECTOR_FIELD']: {'type': 'knn_vector', 'dimension': 1024, 'method': {'name': 'hnsw', 'engine': 'faiss'}},
                    os.environ['TEXT_FIELD']: {'type': 'text'},
                    os.environ['METADATA_FIELD']: {'type': 'text'},
                }
            }
        }
        for attempt in range(10):
            resp = requests.put(url, json=body, auth=auth)
            print(f'Create index attempt {attempt+1}: {resp.status_code} {resp.text}')
            if resp.status_code in (200, 201):
                break
            if resp.status_code == 403:
                time.sleep(10)
                continue
            raise Exception(f'Failed to create index: {resp.status_code} {resp.text}')
        else:
            raise Exception(f'Failed to create index after retries: {resp.status_code} {resp.text}')

    elif request_type == 'Delete':
        resp = requests.delete(url, auth=auth)
        print(f'Delete index: {resp.status_code} {resp.text}')

    return {'PhysicalResourceId': index}
`),
      environment: {
        COLLECTION_ENDPOINT: collection.attrCollectionEndpoint,
        INDEX_NAME: VECTOR_INDEX_NAME,
        VECTOR_FIELD: VECTOR_FIELD_NAME,
        TEXT_FIELD: TEXT_FIELD_NAME,
        METADATA_FIELD: METADATA_FIELD_NAME,
        REGION: this.region,
      },
    });

    const provider = new cr.Provider(this, 'IndexCreatorProvider', {
      onEventHandler: indexCreatorFn,
    });

    const indexCreator = new cdk.CustomResource(this, 'IndexCreator', {
      serviceToken: provider.serviceToken,
    });
    indexCreator.node.addDependency(cfnDataAccessPolicy);

    this.collectionArn = collection.attrArn;
    this.collectionEndpoint = collection.attrCollectionEndpoint;
  }
}
