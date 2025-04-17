import meraki

API_KEY = "USER_API_KEY"
dashboard = meraki.DashboardAPI(API_KEY)

# organization info
organization_response = dashboard.organizations.getOrganizations()
print(organization_response)

# network info
org_id = organization_response[0]['id']
network_id_response = dashboard.organizations.getOrganizationNetworks(org_id)
print(network_id_response)

# device info
device_list_response = dashboard.organizations.getOrganizationDevices(org_id)
# device_info_response = dashboard.organizations.getOrganizationDevicesUplinksAddressesByDevice(org_id, serials=["abcd-bacd-asdf"])
print(device_list_response)
# print(device_info_response)
