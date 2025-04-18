# aruba audit logs
Poll multiple Aruba Central APIs for audit logs. Send data to socket.

## usage
`sudo supervisorctl start aruba-audit-logs`

## system requirements
- [quadrant-rsync-suite](https://github.com/quadrantsec/quadrant-rsync-suite)
	- python3-venv
	- mypip
	- supervisor
- syslog-ng

## continuous deployment
This project should be found on all appliances at: `/usr/local/quadrant/git-py/aruba-audit-logs`

If this is not the case, please ensure that:
- the project has been added to our `git-py` pipeline
- `quadrant-rsync-suite` is properly deployed on the appliance
- `quadrant-rsync-wrapper` is running the `quadrant-rsync-git git-py` task.

## setup
Setup for this project is automated. Simply run the setup script in the project directory!
```
./setup
```

## reference
The sections below are provided as reference.
1. [project configuration](#project-configuration)
    - [app configuration](#app-configuration)
    - [credentials](#credentials)
        1. [credentials.json](#credentialsjson)
        2. [token.json](#tokenjson)
2. [supervisor](#supervisor)
3. [syslog-ng](#syslog-ng)

### project configuration
The project configuration directory is `/usr/local/quadrant/etc/aruba-audit-logs`. Its ownership is set to `nobody:nogroup`.

#### app configuration
Application-specific parameters are located in `app.json` in the project configuration directory. Its ownership is set to `nobody:nogroup`. The default contents are below:
```
{
    "socket_settings": {
        "data_logger": {
            "host": "127.0.0.1",
            "port": 30111,
            "proto": "tcp"
        },
        "app_logger": {
            "unix_sock_path": "/dev/log",
            "proto": "udp"
        }
    },
    "data_collection_settings": {
        "polling_interval_mins": 5,
        "start_time": null
    },
    "is_debug": false,
    "instances": 1
}
```

##### polling interval
The interval between requests is specified by the `polling_interval_mins` field. The field is time in minutes and by default is set to 5 minutes (300 seconds).

##### retroactive retrieval
By default, the application will begin retrieving events one hour prior to the time of the initial run.

Should retroactive retrieval be needed, specify the following parameter:
```
	"start_time": "YYYY-MM-DDTHH:mm:ssZ"
```
For example, if data needs to be retroactively retrieved since June 1, 2023 12:00:00 AM [UTC], specify a `start_time` of `2023-06-01T00:00:00Z`.

Should the deployer need to specify a different start time after the application has already been started, stop the application and delete the hidden `.cache.json` file in the project configuration directory. If running multiple instances, delete all the hidden cache files, e.g. `.cache.json`, `.cache1.json`, etc. Then proceed to restart the application with the retroactive collection time set. However, proceed carefully, as any data already sent to the socket will be resent. This may result in duplication of events.

##### debug mode
By default, debug mode is set to `false`. To run the application in debug mode, set `is_debug` to `true`, and restart the application.

##### instances
By default, instances is set to `1`. To run the application to poll multiple Aruba Central APIs, increase the value of `instances` to the number of Aruba Central instances, update the credentials.json file, create a token.file per instance and restart the application.

#### credentials
In order to make Aruba Central API calls, several parameters and an OAuth access token are required from the customer. See the following sections for a detailed explanation.

##### credentials.json
The `base_url`, `client_id` and `client_secret` parameters are stored in the `credentials.json` file with `0600` permissions in the project configuration directory. A table that lists all of the API Gateway Domain URLs can be found [here](https://www.arubanetworks.com/techdocs/central/latest/content/nms/api/domain_url.htm). The `base_url` parameter must be prefixed with `https://`. The `credentials.json` file should be in the following format:
```
{
    "central_info": {
        "base_url": "https://<api-gateway-domain-url>",
        "client_id": "<api-gateway-client-id>",
        "client_secret": "<api-gateway-client-secret>"
    }
}
```
If running multiple instances, the `credentials.json` file should be in the following format:
```
{
    "central_info": {
        "base_url": "https://<api-gateway-domain-url>",
        "client_id": "<api-gateway-client-id>",
        "client_secret": "<api-gateway-client-secret>"
    },
    "central_info1": {
        "base_url": "https://<api-gateway-domain-url>",
        "client_id": "<api-gateway-client-id>",
        "client_secret": "<api-gateway-client-secret>"
    }
}
```

##### token.json
The OAuth access token is stored in the `token.json` file with `0600` permissions in the project configuration directory. An OAuth access token that is generated in the Aruba Central UI will have a similar format as below and may contain additional properties (fields) such as `appname`, `authenticated_userid`, `credential_id`, `id` and `scope`. The entire OAuth access token from the customer goes in the `token.json` file. After the first token refresh, the `token.json` file should be in the following format:
```
{
    "access_token": "example_access_token",
    "created_at": 1692382088,
    "expires_in": 7200,
    "refresh_token": "example_refresh_token",
    "token_type": "bearer"
}
```
If running multiple instances, there will be a token file per instance. Each token file will be in the same format as the one above. The naming convention will be as follows: `token.json`, `token1.json` (for 2 instances). Verify that any newly created token files have the same permissions and ownership as that of the original `token.json` file, e.g. `0600` permissions and ownership set to `nobody:nogroup`.

### supervisor
Supervisor configuration for the project is located at `/etc/supervisor/conf.d/aruba-audit-logs.conf`. It is created during setup as `root`. The default contents are below:
```
[program:aruba-audit-logs]
# change to project directory, activate virtual environment, execute python program
command = /bin/bash -c 'cd /usr/local/quadrant/git-py/aruba-audit-logs/ && source venv/bin/activate && python main.py'
# run as specified user
user=nobody
# start upon supervisord start
autostart=true
# no retries
startretries=0
# do not restart process upon unexpected exit from running state
autorestart=false
# stop both parent and child processes
stopasgroup=true
# log file locations
stderr_logfile=/var/log/aruba-audit-logs.err.log
stdout_logfile=/var/log/aruba-audit-logs.out.log
```
The setup script reloads the configuration upon editing. If editing manually, please run `sudo supervisorctl update aruba-audit-logs` after saving to reload configuration.

### syslog-ng
Syslog-ng installation is checked during setup. If detected, the setup script will prompt the deployer to locally configure syslog-ng for the project. The configuration will be written to `/etc/syslog-ng/conf.d/aruba-audit-logs.conf`. The setup script will attempt to detect `/var/log/remote/offprem` or `/var/log/remote/off-prem` and use the first one found to exist as the directory for the destination logfile. If neither are detected, the script will prompt the user for a directory. The default contents are below:
```
#SOURCE
source s_aruba-audit-logs {
	network(
		ip("127.0.0.1")
		port(30111)
		transport("tcp")
	);
};

#DESTINATIONS
destination d_aruba-audit-logs {
    file(
		"/var/log/remote/{offprem|off-prem}/aruba-audit-logs-${YEAR}${MONTH}${DAY}.log"
		template("$(format-json --scope nv-pairs --exclude MESSAGE --exclude LEGACY_MSGHDR)\n")
	);
};

#LOG PATHS
log {source(s_aruba-audit-logs); parser{json-parser();}; destination(d_aruba-audit-logs);};
```
Note: The value of the network fields `ip` and `port` should match those specified in the `app.json` found in the project configuration directory. The recommended port to be dedicated to listening for data from this application is 30111.

Note: the collected data are not sent over TLS, so should the listener be on a different appliance from the one running the application, the connection between the two will need to be tunneled.

## commands
### control application
Initial launch: `sudo supervisorctl add aruba-audit-logs`  
Check status: `sudo supervisorctl status aruba-audit-logs`  
Start application: `sudo supervisorctl start aruba-audit-logs`  
Stop application: `sudo supervisorctl stop aruba-audit-logs`  
Restart application: `sudo supervisorctl restart aruba-audit-logs`

### reload configuration
Reload supervisor configuration without starts: `sudo supervisorctl reread`  
Reload supervisor configuration and start process: `sudo supervisorctl update aruba-audit-logs`  
Reload syslog-ng configuration: `sudo syslog-ng-ctl reload`

## logs
Application log: `/var/log/syslog | grep aruba-audit-logs`  
Application stderr: `/var/log/aruba-audit-logs.err.log`