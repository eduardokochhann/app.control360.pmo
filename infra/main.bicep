targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('The location used for all deployed resources')
param location string = resourceGroup().location

param appControl360SouExists bool = false

@description('Client ID of the app registration used to authenticate the app with Entra ID')
param identityProxyClientId string = 'c5b9b4ab-76e8-4f42-abca-bebf57ea1102'

@description('Client secret of the app registration used to authenticate the app with Entra ID')
@secure()
param identityProxyClientSecret string = ''

// Solution from https://www.reddit.com/r/AZURE/comments/159mhzd/how_to_get_the_first_day_of_the_month_for_every/
@description('The first day of the current month, required for Azure Budget startDate (e.g. 2025-07-01)')
param budgetStartDate string = '${utcNow('yyyy-MM')}-01'

var monthlyBudgetReais int = 40

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = uniqueString(resourceGroup().id, location)

var tags = {
  'azd-env-name': environmentName
  Ambiente: 'Produção'
  Custo: 'R$${monthlyBudgetReais}'
  Autorizado: 'Rodrigo Castro'
  Chamado: '12479'
}

var maintainers = [
  {
    email: 'bernardo@sou.cloud'
    objectId: '073f3350-acec-480b-a99e-a5718e4df45d'
  }
  {
    email: 'kocchann@sou.cloud'
    objectId: '357fee7d-3a67-4240-8c48-f4ead81a715f'
  }
]


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

module acrPurgeTask './modules/acr-purge-task.bicep' = {
  name: 'acr-purge-task'
  params: {
    registryName: containerRegistry.outputs.name
    location: location
    tags: tags
    schedule: '0 3 * * *' // daily at 3 AM UTC
    tagsToKeep: 3
  }
}

module keyVault 'br/public:avm/res/key-vault/vault:0.13.0' = {
  name: 'keyVault'
  params: {
    // Required parameters
    name: '${abbrs.keyVaultVaults}${resourceToken}'
    // Non-required parameters
    sku: 'standard'
    enableVaultForTemplateDeployment: true // Allows Bicep to access the vault's secrets
    enablePurgeProtection: false
    roleAssignments: [
      {
        principalId: appControl360SouIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Key Vault Secrets User'
      }
    ]
    secrets: [
      empty(identityProxyClientSecret) ? {
        name: 'placeholder'
        value: 'identity secret was not passed as a parameter in the deployment'
      } : {
        name: 'microsoft-provider-authentication-secret'
        value: identityProxyClientSecret
      }
    ]
  }
}

module fileShareStorageAccount 'br/public:avm/res/storage/storage-account:0.20.0' = {
  name: 'file-share-storage-account'
  params: {
    // Required parameters
    name: '${abbrs.storageStorageAccounts}${resourceToken}'
    // Non-required parameters
    fileServices: {
      shares: [
        {
          enabledProtocols: 'SMB'
          name: 'app-control360-sou-app-data'
          shareQuota: 4 // Quota in GB
        }
        {
          enabledProtocols: 'SMB'
          name: 'app-control360-sou-app-instance'
          shareQuota: 4 // Quota in GB
        }
      ]
    }
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    secretsExportConfiguration: {
      keyVaultResourceId: keyVault.outputs.resourceId
      accessKey1Name: 'stg-appcontrol-360-sou-key1'
    }
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
    roleAssignments: [for user in maintainers: {
      principalId: user.objectId
      roleDefinitionIdOrName: 'Storage Account Contributor'
    }]
  }
}

// Container apps environment
module containerAppsEnvironment 'br/public:avm/res/app/managed-environment:0.11.2' = {
  name: 'container-apps-environment'
  params: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    zoneRedundant: false
    storages: [
      {
        accessMode: 'ReadWrite'
        kind: 'SMB'
        shareName: 'app-control360-sou-app-data'
        storageAccountName: fileShareStorageAccount.outputs.name
      }
      {
        accessMode: 'ReadWrite'
        kind: 'SMB'
        shareName: 'app-control360-sou-app-instance'
        storageAccountName: fileShareStorageAccount.outputs.name
      }
    ]
    publicNetworkAccess: 'Enabled'
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

module appControl360Sou 'br/public:avm/res/app/container-app:0.17.0' = {
  name: 'appControl360Sou'
  params: {
    name: 'app-control360-sou'
    ingressTargetPort: 5000
    secrets: [
      {
        keyVaultUrl: '${keyVault.outputs.uri}secrets/stg-appcontrol-360-sou-key1'
        identity: appControl360SouIdentity.outputs.resourceId
        name: 'stg-appcontrol-360-sou-key1'
      }
      {
        keyVaultUrl: '${keyVault.outputs.uri}secrets/microsoft-provider-authentication-secret'
        identity: appControl360SouIdentity.outputs.resourceId
        name: 'microsoft-provider-authentication-secret'
      }
    ]
    scaleSettings: {
      minReplicas: 0
      maxReplicas: 1
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
            name: 'AZURE_CLIENT_ID'
            value: appControl360SouIdentity.outputs.clientId
          }
          {
            name: 'PORT'
            value: '5000'
          }
        ]
        volumeMounts: [
          {
            volumeName: 'app-data'
            mountPath: '/app/data'
          }
          {
            volumeName: 'app-instance'
            mountPath: '/app/instance'
          }
        ]
      }
    ]
    volumes: [
      {
        name: 'app-data'
        storageName: 'app-control360-sou-app-data' // Autogenerated from environment name
        storageType: 'AzureFile'
      }
      {
        name: 'app-instance'
        storageName: 'app-control360-sou-app-instance' // Autogenerated from environment name
        storageType: 'AzureFile'
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
    authConfig: {
      platform: {
        enabled: true
      }
      globalValidation: {
        unauthenticatedClientAction: 'RedirectToLoginPage'
        redirectToProvider: 'azureactivedirectory'
      }
      identityProviders: {
        azureActiveDirectory: {
          registration: {
            openIdIssuer: 'https://sts.windows.net/a7220fd8-b71b-44f9-b153-117f6a6a7b2f/v2.0'
            clientId: identityProxyClientId
            clientSecretSettingName: 'microsoft-provider-authentication-secret'
          }
        }
      }
    }
    roleAssignments: [for user in maintainers: {
      principalId: user.objectId
      roleDefinitionIdOrName: '358470bc-b998-42bd-ab17-a7e34c199c0f' // Container Apps Contributor
    }]
  }
}


// Azure Budget: Cap spending at R$40 per month
// The startDate is when the budget begins tracking. It must be the first day of the current month.
resource monthlyBudget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'monthly-budget-r40'
  scope: resourceGroup()
  properties: {
    category: 'Cost'
    amount: monthlyBudgetReais
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate // Must be the first day of the current month
    }
    notifications: {
      actualGt80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: [ for user in maintainers: user.email ]
      }
      actualGt100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: [ for user in maintainers: user.email ]
      }
      forecastedGt120: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 120
        contactEmails: [ for user in maintainers: user.email ]
        thresholdType: 'Forecasted'
      }
    }
  }
}

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_RESOURCE_APP_CONTROL360_SOU_ID string = appControl360Sou.outputs.resourceId
