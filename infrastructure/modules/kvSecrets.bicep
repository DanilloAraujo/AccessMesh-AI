/*
  Stores all sensitive connection strings and keys as Key Vault secrets.
  Keys are written directly from the outputs of other modules.
  In production, prefer using managed identities + Key Vault references
  instead of passing raw key values — this module is a convenience for dev/staging.
*/

param keyVaultName string

@secure()
param cosmosEndpoint string
@secure()
param cosmosKey string
@secure()
param serviceBusConnectionString string
@secure()
param webPubSubConnectionString string
@secure()
param speechKey string
@secure()
param openAiKey string
@secure()
param openAiEndpoint string
@secure()
param contentSafetyKey string
@secure()
param contentSafetyEndpoint string
@secure()
param translatorKey string
@secure()
param appInsightsConnectionString string

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource secretCosmosEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'cosmos-endpoint'
  properties: { value: cosmosEndpoint }
}

resource secretCosmosKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'cosmos-key'
  properties: { value: cosmosKey }
}

resource secretServiceBus 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'servicebus-connection-string'
  properties: { value: serviceBusConnectionString }
}

resource secretWebPubSub 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'webpubsub-connection-string'
  properties: { value: webPubSubConnectionString }
}

resource secretSpeechKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'azure-speech-key'
  properties: { value: speechKey }
}

resource secretOpenAiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'azure-openai-key'
  properties: { value: openAiKey }
}

resource secretOpenAiEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'azure-openai-endpoint'
  properties: { value: openAiEndpoint }
}

resource secretContentSafetyKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'content-safety-key'
  properties: { value: contentSafetyKey }
}

resource secretContentSafetyEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'content-safety-endpoint'
  properties: { value: contentSafetyEndpoint }
}

resource secretTranslatorKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'translator-key'
  properties: { value: translatorKey }
}

resource secretAppInsights 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'appinsights-connection-string'
  properties: { value: appInsightsConnectionString }
}
