import os
import meraki

# CS09N organization key
API_KEY = os.environ.get('DB_KEY')

# create dashboard object and get organizations
print("\nInitialising dashboard:\n")
dashboard = meraki.DashboardAPI(API_KEY)
organizations = dashboard.organizations.getOrganizations()

output_string = ""

# get networks and devices for each organization (only one)
for org in organizations:

    # add organization to output
    output_string += f'\nOrganisations:-\n\tName: {org["name"]}\n\t'
    admins = dashboard.organizations.getOrganizationAdmins(org["id"])
    output_string += 'Admins: ' +  ", ".join([ admin["name"] for admin in admins])

    # get networks in organization
    print(f'\nGetting data from organization {org["name"]}:\n')
    networks = dashboard.organizations.getOrganizationNetworks(org['id'])

    # add network to output string
    output_string += '\n\tNetworks:-'
    for net in networks:
        output_string += "\n\t\t".join(["",f'Name: {net["name"]}',f'Timezone: {net["timeZone"]}',f'ID: {net["id"]}'])

        # get devices on the network
        print(f'\nGetting devices from network {net["name"]}:\n')
        devices = dashboard.networks.getNetworkDevices(net['id'])
        
        # add device to output string
        output_string += f'\n\t\tDevices:-'
        for dev in devices:
            output_string += "\n\t\t\t".join(["",f'Name: {dev["name"]}',f'Model: {dev["model"]}',f'MAC: {dev["mac"]}'])

            # get clients on device
            print(f'\nGetting clients from device {dev["name"]}:\n')
            clients = dashboard.devices.getDeviceClients(dev["serial"])

            # add client to output string
            output_string += f'\n\t\t\tClients:-'
            for client in clients:
                output_string += "\n\t\t\t\t".join(["",f'Name: {client["dhcpHostname"]}',f'IP: {client["ip"]}',f'Usage: {str(client["usage"])}\n'])

print(output_string)