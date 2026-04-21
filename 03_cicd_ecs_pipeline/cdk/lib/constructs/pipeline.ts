import { Construct } from "constructs";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as codebuild from "aws-cdk-lib/aws-codebuild";
import * as codedeploy from "aws-cdk-lib/aws-codedeploy";
import * as codepipeline from "aws-cdk-lib/aws-codepipeline";
import * as codepipeline_actions from "aws-cdk-lib/aws-codepipeline-actions";
import * as iam from "aws-cdk-lib/aws-iam";

export interface PipelineConstructProps {
  readonly envName: string;
  readonly service: ecs.FargateService;
  readonly repository: ecr.Repository;
  readonly blueTargetGroup: elbv2.ApplicationTargetGroup;
  readonly greenTargetGroup: elbv2.ApplicationTargetGroup;
  readonly productionListener: elbv2.ApplicationListener;
  readonly testListener: elbv2.ApplicationListener;
  /** ECS タスク定義の family 名 */
  readonly taskDefinitionFamily: string;
  /** コンテナ名（taskdef.json の containerName と一致させる） */
  readonly containerName: string;
}

export class PipelineConstruct extends Construct {
  constructor(scope: Construct, id: string, props: PipelineConstructProps) {
    super(scope, id);

    const application = new codedeploy.EcsApplication(this, "CodeDeployApp", {
      applicationName: `${props.envName}-pipeline-app`,
    });

    const deploymentGroup = new codedeploy.EcsDeploymentGroup(this, "DeploymentGroup", {
      application,
      deploymentGroupName: `${props.envName}-pipeline-dg`,
      service: props.service,
      blueGreenDeploymentConfig: {
        blueTargetGroup: props.blueTargetGroup,
        greenTargetGroup: props.greenTargetGroup,
        listener: props.productionListener,
        testListener: props.testListener,
      },
      deploymentConfig: codedeploy.EcsDeploymentConfig.ALL_AT_ONCE,
    });

    // ECR Source が出力する imageDetail.json から imageUri を取り出し
    // appspec.yaml と taskdef.json を動的生成する CodeBuild プロジェクト
    const buildProject = new codebuild.PipelineProject(this, "BuildProject", {
      projectName: `${props.envName}-pipeline-build`,
      environment: {
        buildImage: codebuild.LinuxBuildImage.STANDARD_7_0,
      },
      environmentVariables: {
        TASK_DEFINITION_FAMILY: { value: props.taskDefinitionFamily },
        CONTAINER_NAME: { value: props.containerName },
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: "0.2",
        phases: {
          build: {
            commands: [
              // 現在のタスク定義を取得してイメージを <IMAGE1_NAME> プレースホルダーに差し替え
              "aws ecs describe-task-definition --task-definition $TASK_DEFINITION_FAMILY --query taskDefinition > taskdef.json",
              "python3 -c \"import json; d=json.load(open('taskdef.json')); [c.update({'image': '<IMAGE1_NAME>'}) for c in d['containerDefinitions'] if c['name']=='$CONTAINER_NAME']; json.dump(d, open('taskdef.json','w'))\"",
              // appspec.yaml を生成
              "echo 'version: 0.0' > appspec.yaml",
              "echo 'Resources:' >> appspec.yaml",
              "echo '  - TargetService:' >> appspec.yaml",
              "echo '      Type: AWS::ECS::Service' >> appspec.yaml",
              "echo '      Properties:' >> appspec.yaml",
              "echo '        TaskDefinition: <TASK_DEFINITION>' >> appspec.yaml",
              "echo '        LoadBalancerInfo:' >> appspec.yaml",
              `echo '          ContainerName: ${props.containerName}' >> appspec.yaml`,
              "echo '          ContainerPort: 80' >> appspec.yaml",
            ],
          },
        },
        artifacts: {
          files: ["appspec.yaml", "taskdef.json"],
        },
      }),
    });

    // CodeBuild に ECS タスク定義の読み取り権限を付与
    buildProject.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["ecs:DescribeTaskDefinition"],
        resources: ["*"],
      }),
    );

    const ecrSourceOutput = new codepipeline.Artifact("EcrSource");
    const buildOutput = new codepipeline.Artifact("BuildOutput");

    new codepipeline.Pipeline(this, "Pipeline", {
      pipelineName: `${props.envName}-ecs-pipeline`,
      pipelineType: codepipeline.PipelineType.V2,
      stages: [
        {
          stageName: "Source",
          actions: [
            new codepipeline_actions.EcrSourceAction({
              actionName: "ECR_Source",
              repository: props.repository,
              imageTag: "latest",
              output: ecrSourceOutput,
            }),
          ],
        },
        {
          stageName: "Build",
          actions: [
            new codepipeline_actions.CodeBuildAction({
              actionName: "Generate_AppSpec_TaskDef",
              project: buildProject,
              input: ecrSourceOutput,
              outputs: [buildOutput],
            }),
          ],
        },
        {
          stageName: "Deploy",
          actions: [
            new codepipeline_actions.CodeDeployEcsDeployAction({
              actionName: "CodeDeploy_BlueGreen",
              deploymentGroup,
              containerImageInputs: [
                {
                  input: ecrSourceOutput,
                  taskDefinitionPlaceholder: "IMAGE1_NAME",
                },
              ],
              taskDefinitionTemplateInput: buildOutput,
              appSpecTemplateInput: buildOutput,
            }),
          ],
        },
      ],
    });
  }
}
