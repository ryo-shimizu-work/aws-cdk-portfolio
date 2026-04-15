import * as cdk from 'aws-cdk-lib/core';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import { Construct } from 'constructs';
import { parameter } from '../parameter';
import { VECTOR_INDEX_NAME, VECTOR_FIELD_NAME, TEXT_FIELD_NAME, METADATA_FIELD_NAME } from './opensearch-stack';

const EMBEDDING_MODEL_ARN = parameter.models.embedding;

interface KnowledgeBaseStackProps extends cdk.StackProps {
  documentBucket: s3.Bucket;
  collectionArn: string;
  knowledgeBaseRole: iam.Role;
}

export class KnowledgeBaseStack extends cdk.Stack {
  public readonly knowledgeBaseId: string;
  public readonly knowledgeBaseArn: string;
  public readonly dataSourceId: string;

  constructor(scope: Construct, id: string, props: KnowledgeBaseStackProps) {
    super(scope, id, props);

    // Bedrock Knowledge Base
    const knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', {
      name: 'rag-knowledge-base',
      roleArn: props.knowledgeBaseRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: EMBEDDING_MODEL_ARN,
        },
      },
      storageConfiguration: {
        type: 'OPENSEARCH_SERVERLESS',
        opensearchServerlessConfiguration: {
          collectionArn: props.collectionArn,
          vectorIndexName: VECTOR_INDEX_NAME,
          fieldMapping: {
            vectorField: VECTOR_FIELD_NAME,
            textField: TEXT_FIELD_NAME,
            metadataField: METADATA_FIELD_NAME,
          },
        },
      },
    });

    // S3をデータソースとして登録
    const dataSource = new bedrock.CfnDataSource(this, 'DataSource', {
      knowledgeBaseId: knowledgeBase.attrKnowledgeBaseId,
      name: 'rag-s3-datasource',
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: props.documentBucket.bucketArn,
        },
      },
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: 'FIXED_SIZE',
          fixedSizeChunkingConfiguration: {
            maxTokens: 300,
            overlapPercentage: 20,
          },
        },
      },
    });

    this.knowledgeBaseId = knowledgeBase.attrKnowledgeBaseId;
    this.knowledgeBaseArn = knowledgeBase.attrKnowledgeBaseArn;
    this.dataSourceId = dataSource.attrDataSourceId;

    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: knowledgeBase.attrKnowledgeBaseId,
      exportName: 'KnowledgeBaseId',
    });
    new cdk.CfnOutput(this, 'DataSourceId', {
      value: dataSource.attrDataSourceId,
      exportName: 'DataSourceId',
    });
  }
}
