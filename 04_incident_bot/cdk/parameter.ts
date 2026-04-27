import * as dotenv from 'dotenv';
dotenv.config();

if (!process.env.SLACK_WEBHOOK_URL) {
  throw new Error('SLACK_WEBHOOK_URL が .env に設定されていません');
}

export const parameter = {
  accountId: "<AWS_ACCOUNT_ID>",
  region: "ap-northeast-1",
  slack: {
    webhookUrl: process.env.SLACK_WEBHOOK_URL,
  },
  bedrock: {
    modelId: "amazon.nova-lite-v1:0",
  },
  logGroup: {
    name: "/incident-bot/app",
    // Logs Insights でログを取得する範囲（分）
    lookbackMinutes: 30,
  },
};
