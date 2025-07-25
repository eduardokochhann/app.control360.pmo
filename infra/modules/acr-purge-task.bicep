@description('The name of the container registry')
param registryName string

@description('The location for the task')
param location string

@description('Tags to apply to the task')
param tags object = {}

@description('Cron schedule for the purge task (e.g. "0 3 * * *" for daily at 3 AM UTC)')
param schedule string = '0 3 * * *'

@description('Number of recent tags to keep per repository')
param tagsToKeep int = 3

resource acrPurgeTask 'Microsoft.ContainerRegistry/registries/tasks@2025-03-01-preview' = {
  name: '${registryName}/purge-old-tags'
  location: location
  properties: {
    status: 'Enabled'
    platform: {
      os: 'Linux'
      architecture: 'amd64'
    }
    step: {
      type: 'EncodedTask'
      encodedTaskContent: base64('acr purge --filter \'.*:.*\' --untagged --ago 0d --keep 3')
    }
    agentConfiguration: {
      cpu: 2
    }
    timeout: 600
    trigger: {
      timerTriggers: [
        {
          name: 'purge-schedule'
          schedule: schedule
          status: 'Enabled'
        }
      ]
    }
  }
  tags: tags
}
