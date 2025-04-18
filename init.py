import atexit
import logging
import os
import signal
import stat
import sys
import time
from pathlib import Path
from calendar import timegm
from threading import Event

from aruba.base import ArubaCentralBase
from aruba.audit_logs import Audit

import qlib.json
import qlib.logging
from qlib.socket import lookup_sock_kind

source = Path(__file__).absolute()
project_name = source.parent.name

audit_list          = []
central_list        = []
central_info_list   = []
cache_list          = []
cache_path_list     = []
token_path_list     = []

# path to project etc directory
project_etc = os.path.join(source.parents[2], 'etc', project_name)

base_cache_path = os.path.join(project_etc, '.cache')
base_token_path = os.path.join(project_etc, 'token')
file_suffix     = '.json'
exit_flag       = Event()

# retrieve app config
app_config_path = os.path.join(project_etc, 'app.json')
app_config = qlib.json.load(app_config_path)
socket_settings = app_config['socket_settings']
polling_interval_mins = app_config['data_collection_settings']['polling_interval_mins']
start_time = app_config['data_collection_settings']['start_time']

if start_time:
	try:
		struct_time = time.strptime(start_time, "%Y-%m-%dT%H:%M:%SZ")
		start_time = timegm(struct_time)
	except ValueError:
		start_time = None

# set logger address
for logger in socket_settings:
	if socket_settings[logger].get('unix_sock_path'):
		socket_settings[logger]['address'] = socket_settings[logger]['unix_sock_path']
	else:
		socket_settings[logger]['address'] = (
			socket_settings[logger]['host'],
			socket_settings[logger]['port'])

# retrieve credentials
credentials_path = os.path.join(project_etc, 'credentials.json')
credentials = qlib.json.load(credentials_path)

for credential in credentials:
	central_info_list.append(credentials[credential])

# configure app main and backup logger
logging_level = logging.INFO
if app_config.get('is_debug'):
	logging_level = logging.DEBUG

num_instances = app_config.get('instances', 1)

app_logger = qlib.logging.configure_logger(
		project_name,
		level = logging_level,
		address = socket_settings['app_logger']['address'],
		socktype = lookup_sock_kind(socket_settings['app_logger']['proto']))
# configure data logger
data_logger = qlib.logging.configure_logger(
		f'{project_name}_data',
		handler_class = qlib.logging.ReconnectingSysLogHandler,
		address = socket_settings['data_logger']['address'],
		socktype = lookup_sock_kind(socket_settings['data_logger']['proto']))

for i in range(num_instances):
	if i == 0:
		cache_path_list.append(f'{base_cache_path}{file_suffix}')
		token_path_list.append(f'{base_token_path}{file_suffix}')
	else:
		cache_path_list.append(f'{base_cache_path}{i}{file_suffix}')
		token_path_list.append(f'{base_token_path}{i}{file_suffix}')

for j in range(num_instances):
	audit_list.append(Audit())

	# Aruba Central base class
	central = ArubaCentralBase(central_info = central_info_list[j],
							   token_store  = token_path_list[j],
							   logger       = app_logger,
							   user_retries = 3)
	central_list.append(central)

	try:
		cache = qlib.json.load(cache_path_list[j])
	except FileNotFoundError:
		cache = {
			"last_time": None,
			"last_data": []
		}

	# default last time to start time if not set or adjust by one hour
	if not cache['last_time']:
		last_time = int(time.time()) - 3600
		if start_time and start_time < last_time:
			last_time = start_time
		cache['last_time'] = last_time
	else:
		# if last time not older than one day, use it
		last_time = int(time.time()) - 86400
		if cache['last_time'] > last_time:
			last_time = cache['last_time']
		cache['last_time'] = last_time

	cache_list.append(cache)

# handle app shutdown
@atexit.register
def save_cache():
	for k in range(num_instances):
		# save to file
		qlib.json.dump(cache_list[k], cache_path_list[k])
		# ensure file read-only by owner
		os.chmod(cache_path_list[k], stat.S_IRUSR | stat.S_IWUSR)
		app_logger.info(f'Saved app cache to {cache_path_list[k]}')

# handle termination signals
def handle_termination_signal(signum, frame):
	if (num_instances > 1):
	    exit_flag.set()
	app_logger.info(f'Received termination signal {signum} at frame {frame}')
	sys.exit(0)

signal.signal(signal.SIGTERM, handle_termination_signal)
signal.signal(signal.SIGINT, handle_termination_signal)