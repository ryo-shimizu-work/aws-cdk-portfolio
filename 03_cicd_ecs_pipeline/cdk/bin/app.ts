#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { PipelineStack } from "../lib/pipeline-stack";
import { parameter } from "../parameter";

const app = new cdk.App();

new PipelineStack(app, "CicdEcsPipelineStack", {
  envName: "dev",
  env: {
    account: parameter.accountId,
    region: parameter.region,
  },
  ...parameter,
});
