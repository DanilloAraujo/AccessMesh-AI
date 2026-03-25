/*
  AccessMesh-AI — Azure infrastructure
  =====================================
  Provisions all resources required by the application.

  Deploy:
    az deployment sub create \
      --location eastus \
      --template-file infrastructure/main.bicep \
      --parameters @infrastructure/main.bicepparam
*/

targetScope = 'subscription'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Short environment label: dev | staging | prod')
@allowed(['dev', 'staging', 'prod'])
param env string = 'dev'

@description('Azure region for all resources.')
param location string = 'eastus'

@description('Base name used to build all resource names.')
@minLength(3)
@maxLength(16)
param projectName string = 'accessmesh'

@description('Object ID of the AAD principal (user / service-principal / managed identity) that should be granted Key Vault admin access.')
param kvAdminObjectId string

@description('Comma-separated list of allowed CORS origins for the backend, e.g. "https://myapp.azurestaticapps.net"')
param corsOrigins string = 'http://localhost:5173'

// ---------------------------------------------------------------------------
// Variables
// ---------------------------------------------------------------------------

var nameSuffix = '${projectName}-${env}'
var rgName = 'rg-${nameSuffix}'
var tags = {
  project: projectName
  environment: env
  managedBy: 'bicep'
}

// ---------------------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------------------

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: rgName
  location: location
  tags: tags
}

// ---------------------------------------------------------------------------
// Modules
// ---------------------------------------------------------------------------

module logAnalytics 'modules/logAnalytics.bicep' = {
  name: 'logAnalytics'
  scope: rg
  params: {
    name: 'log-${nameSuffix}'
    location: location
    tags: tags
  }
}

module appInsights 'modules/appInsights.bicep' = {
  name: 'appInsights'
  scope: rg
  params: {
    name: 'appi-${nameSuffix}'
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

module keyVault 'modules/keyVault.bicep' = {
  name: 'keyVault'
  scope: rg
  params: {
    name: 'kv-${nameSuffix}'
    location: location
    adminObjectId: kvAdminObjectId
    tags: tags
  }
}

module containerRegistry 'modules/containerRegistry.bicep' = {
  name: 'containerRegistry'
  scope: rg
  params: {
    name: 'cr${replace(nameSuffix, '-', '')}' // ACR names: alphanumeric only
    location: location
    tags: tags
  }
}

module cosmosDb 'modules/cosmosDb.bicep' = {
  name: 'cosmosDb'
  scope: rg
  params: {
    accountName: 'cosmos-${nameSuffix}'
    location: location
    tags: tags
  }
}

module serviceBus 'modules/serviceBus.bicep' = {
  name: 'serviceBus'
  scope: rg
  params: {
    namespaceName: 'sb-${nameSuffix}'
    location: location
    tags: tags
  }
}

module webPubSub 'modules/webPubSub.bicep' = {
  name: 'webPubSub'
  scope: rg
  params: {
    name: 'wps-${nameSuffix}'
    location: location
    tags: tags
  }
}

module speechService 'modules/speechService.bicep' = {
  name: 'speechService'
  scope: rg
  params: {
    name: 'speech-${nameSuffix}'
    location: location
    tags: tags
  }
}

module openAi 'modules/openAi.bicep' = {
  name: 'openAi'
  scope: rg
  params: {
    name: 'oai-${nameSuffix}'
    location: location
    tags: tags
  }
}

module contentSafety 'modules/contentSafety.bicep' = {
  name: 'contentSafety'
  scope: rg
  params: {
    name: 'cs-${nameSuffix}'
    location: location
    tags: tags
  }
}

module translator 'modules/translator.bicep' = {
  name: 'translator'
  scope: rg
  params: {
    name: 'tr-${nameSuffix}'
    location: location
    tags: tags
  }
}

module containerAppsEnv 'modules/containerAppsEnv.bicep' = {
  name: 'containerAppsEnv'
  scope: rg
  params: {
    name: 'cae-${nameSuffix}'
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    appInsightsConnectionString: appInsights.outputs.connectionString
    tags: tags
  }
}

module backendApp 'modules/backendApp.bicep' = {
  name: 'backendApp'
  scope: rg
  params: {
    name: 'ca-backend-${nameSuffix}'
    location: location
    containerAppsEnvId: containerAppsEnv.outputs.envId
    acrLoginServer: containerRegistry.outputs.loginServer
    acrName: containerRegistry.outputs.name
    keyVaultName: keyVault.outputs.name
    appInsightsConnectionString: appInsights.outputs.connectionString
    corsOrigins: corsOrigins
    tags: tags
  }
}

module staticWebApp 'modules/staticWebApp.bicep' = {
  name: 'staticWebApp'
  scope: rg
  params: {
    name: 'swa-${nameSuffix}'
    location: location
    tags: tags
  }
}

// ---------------------------------------------------------------------------
// Key Vault secrets (connection strings / keys)
// ---------------------------------------------------------------------------

module kvSecrets 'modules/kvSecrets.bicep' = {
  name: 'kvSecrets'
  scope: rg
  params: {
    keyVaultName: keyVault.outputs.name
    cosmosEndpoint: cosmosDb.outputs.endpoint
    cosmosKey: cosmosDb.outputs.primaryKey
    serviceBusConnectionString: serviceBus.outputs.connectionString
    webPubSubConnectionString: webPubSub.outputs.connectionString
    speechKey: speechService.outputs.key
    openAiKey: openAi.outputs.key
    openAiEndpoint: openAi.outputs.endpoint
    contentSafetyKey: contentSafety.outputs.key
    contentSafetyEndpoint: contentSafety.outputs.endpoint
    translatorKey: translator.outputs.key
    appInsightsConnectionString: appInsights.outputs.connectionString
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------

output resourceGroupName string = rg.name
output backendUrl string = backendApp.outputs.url
output staticWebAppDefaultHostname string = staticWebApp.outputs.defaultHostname
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
output keyVaultName string = keyVault.outputs.name
output cosmosEndpoint string = cosmosDb.outputs.endpoint
