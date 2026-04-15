import * as cdk from "aws-cdk-lib/core";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";
import { parameter } from "../parameter";

interface ComputeStackProps extends cdk.StackProps {
  knowledgeBaseId: string;
  knowledgeBaseArn: string;
}

export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    const fn = new lambda.Function(this, "RagFunction", {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: "index.handler",
      code: lambda.Code.fromInline(`
import boto3
import os

client = boto3.client('bedrock-agent-runtime')
KNOWLEDGE_BASE_ID = os.environ['KNOWLEDGE_BASE_ID']
MODEL_ARN = os.environ['MODEL_ARN']

def handler(event, context):
    query = event.get('query', '')
    response = client.retrieve_and_generate(
        input={'text': query},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                'modelArn': MODEL_ARN,
            },
        },
    )
    return {
        'answer': response['output']['text'],
        'citations': response.get('citations', []),
    }
`),
      environment: {
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId,
        MODEL_ARN: parameter.models.generation,
      },
      timeout: cdk.Duration.seconds(30),
    });

    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:RetrieveAndGenerate"],
        resources: ["*"],
      }),
    );

    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:Retrieve"],
        resources: [props.knowledgeBaseArn],
      }),
    );

    fn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["bedrock:InvokeModel"],
        resources: [parameter.models.generation],
      }),
    );

    new cdk.CfnOutput(this, 'RagFunctionName', {
      value: fn.functionName,
      exportName: 'RagFunctionName',
    });
  }
}
