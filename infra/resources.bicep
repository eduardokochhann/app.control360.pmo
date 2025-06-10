@description('The location used for all deployed resources')
param location string = resourceGroup().location

@description('Tags that will be applied to all resources')
param tags object = {}


param appControl360SouExists bool

@description('Id of the user or app to assign application roles')
param principalId string

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location)

// Monitor application with Azure Monitor
module monitoring 'br/public:avm/ptn/azd/monitoring:0.1.0' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    applicationInsightsDashboardName: '${abbrs.portalDashboards}${resourceToken}'
    location: location
    tags: tags
    enableTelemetry: false
  }
}
// Container registry
module containerRegistry 'br/public:avm/res/container-registry/registry:0.1.1' = {
  name: 'registry'
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    publicNetworkAccess: 'Enabled'
    roleAssignments:[
      {
        principalId: appControl360SouIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
      }
    ]
  }
}

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.4.5' = {
  name: 'container-apps-environment'
  params: {
    logAnalyticsWorkspaceResourceId: monitoring.outputs.logAnalyticsWorkspaceResourceId
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
  }
}

module appControl360SouIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.2.1' = {
  name: 'appControl360Souidentity'
  params: {
    name: '${abbrs.managedIdentityUserAssignedIdentities}appControl360Sou-${resourceToken}'
    location: location
  }
}
module appControl360SouFetchLatestImage './modules/fetch-container-image.bicep' = {
  name: 'appControl360Sou-fetch-image'
  params: {
    exists: appControl360SouExists
    name: 'app-control360-sou'
  }
}

module appControl360Sou 'br/public:avm/res/app/container-app:0.8.0' = {
  name: 'appControl360Sou'
  params: {
    name: 'app-control360-sou'
    ingressTargetPort: 5000
    scaleMinReplicas: 0
    scaleMaxReplicas: 1
    secrets: {
      secureList:  [
      ]
    }
    containers: [
      {
        image: appControl360SouFetchLatestImage.outputs.?containers[?0].?image ?? 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
        name: 'main'
        resources: {
          cpu: json('0.5')
          memory: '1.0Gi'
        }
        env: [
          {
            name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
            value: monitoring.outputs.applicationInsightsConnectionString
          }
          {
            name: 'AZURE_CLIENT_ID'
            value: appControl360SouIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '5000'
          }
        ]
      }
    ]
    managedIdentities:{
      systemAssigned: false
      userAssignedResourceIds: [appControl360SouIdentity.outputs.resourceId]
    }
    registries:[
      {
        server: containerRegistry.outputs.loginServer
        identity: appControl360SouIdentity.outputs.resourceId
      }
    ]
    environmentResourceId: containerAppsEnvironment.outputs.resourceId
    location: location
    tags: union(tags, { 'azd-service-name': 'app-control360-sou' })
    ipSecurityRestrictions: [
          {
            name: 'allow-azure-services'
            ipAddressRange: '48.214.20.129'
            action: 'Allow'
          }
    ]
  }
}
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_APP_CONTROL360_SOU_ID string = appControl360Sou.outputs.resourceId
