#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { AppStack } from "../lib/app-stack";
import { parameter } from "../parameter";

const app = new cdk.App();

new AppStack(app, "EcsWebAppStack", {
  envName: "dev",
  env: {
    // CDK_DEFAULT_ACCOUNT / CDK_DEFAULT_REGION を使う場合は cdk bootstrap が必要
    account: parameter.accountId,
    region: parameter.region,
  },
  ...parameter,
});
