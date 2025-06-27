targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

param appControl360SouExists bool

@description('Id of the user or app to assign application roles')
param principalId string

@description('Client ID of the app registration used to authenticate the app with Entra ID')
param identityProxyClientId string = 'c5b9b4ab-76e8-4f42-abca-bebf57ea1102'

@description('Client secret of the app registration used to authenticate the app with Entra ID')
@secure()
param identityProxyClientSecret string

// Tags that should be applied to all resources.
// 
// Note that 'azd-service-name' tags should be applied separately to service host resources.
// Example usage:
//   tags: union(tags, { 'azd-service-name': <service name in azure.yaml> })
var tags = {
  'azd-env-name': environmentName
}

// Organize resources in a resource group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  scope: rg
  name: 'resources'
  params: {
    location: location
    tags: tags
    principalId: principalId
    appControl360SouExists: appControl360SouExists
    identityProxyClientId: identityProxyClientId
    identityProxyClientSecret: identityProxyClientSecret
  }
}
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.AZURE_CONTAINER_REGISTRY_ENDPOINT
output AZURE_RESOURCE_APP_CONTROL360_SOU_ID string = resources.outputs.AZURE_RESOURCE_APP_CONTROL360_SOU_ID
