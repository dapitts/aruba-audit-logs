import json
import time
from threading import Thread, Event

import init
from init import num_instances, audit_list, central_list, polling_interval_mins, app_logger, data_logger

def get_event_logs(index):
    audit   = audit_list[index]
    central = central_list[index]

    while True:
        start_time = init.cache_list[index]['last_time']

        try:
            # get audit events for all groups, sort by time in reverse chronological order
            resp = audit.get_eventlogs(central, start_time = start_time)

            if resp['code'] == 200:
                total = resp['msg']['total']

                if total:
                    # filter out any duplicate events
                    events = [event for event in resp['msg']['events'] if event['id'] not in init.cache_list[index]['last_data']]
                    count = len(events)

                    if count:
                        first_ts = events[0]['ts']

                        # do more events need to be fetched for the time range starting with start_time
                        if resp['msg']['remaining_records']:
                            last_ts = events[-1]['ts']
                            last_ts_ids = get_event_ts_ids(events, last_ts)
                            finished = False

                            while not finished:
                                # get audit events for all groups, sort by time in reverse chronological order
                                resp2 = audit.get_eventlogs(central, start_time = start_time, end_time = last_ts)

                                if resp2['code'] == 200:
                                    finished = not resp2['msg']['remaining_records']
                                    # filter out duplicate events
                                    events2 = [event for event in resp2['msg']['events'] if event['id'] not in last_ts_ids]
                                    events.extend(events2)

                                    if not finished:
                                        last_ts = events2[-1]['ts']
                                        last_ts_ids = get_event_ts_ids(events2, last_ts)
                                else:
                                    app_logger.debug(f'get_eventlogs(2) failed with response {json.dumps(resp2["msg"])}')

                        init.cache_list[index]['last_data'].clear()

                        # iterate over events in reverse order
                        for event in reversed(events):
                            if event['has_details']:
                                # get details of an audit event/log
                                resp3 = audit.get_eventlogs_detail(central, event['id'])

                                if resp3['code'] == 200:
                                    event['details'] = resp3['msg']['data']
                                else:
                                    event['details'] = {}
                                    app_logger.debug(f'get_eventlogs_detail() failed with response {json.dumps(resp3["msg"])}')
                            else:
                                event['details'] = {}

                            # send to socket
                            data_logger.info(json.dumps(event))
                            # cache processed event id
                            init.cache_list[index]['last_data'].append(event['id'])

                        init.cache_list[index]['last_time'] = first_ts
                    else:
                        # increment last_time by 1 to stop fetching event(s) with ts equal to first_ts
                        init.cache_list[index]['last_time'] += 1
            else:
                app_logger.debug(f'get_eventlogs(1) failed with response {json.dumps(resp["msg"])}')

        except Exception as err:
            app_logger.debug(f'main() exception {str(err)}')

        # wait before next poll
        if (num_instances == 1):
            time.sleep(polling_interval_mins * 60)
        else:
            if (init.exit_flag.wait(polling_interval_mins * 60)):
                break

def main():
    if (num_instances == 1):
        get_event_logs(0)
    else:
        threads = []

        for i in range(num_instances):
            threads.append(Thread(target=get_event_logs, args=(i, )))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

def get_event_ts_ids(events, ts, reverse = True):
    ids = []
    events_list = reversed(events) if reverse else events

    for event in events_list:
        if event['ts'] == ts:
            ids.append(event['id'])
        else:
            break

    return ids

main()