import MySQLdb
import MySQLdb.cursors

import os
import iso8601
import time
import sys
import json
import random
import logging

import docker

from datetime import datetime, timedelta

from settings import MYSQL_DATABASE_USER, MYSQL_DATABASE_PASSWORD, \
    MYSQL_DATABASE_DB, REMOTE_DOCKER_DAEMON_PORT, \
    DOCKER_DISTRIBUTION_SERVER, DOCKER_DISTRIBUTION_USER, \
    DOCKER_DISTRIBUTION_PASS, DOCKER_DISTRIBUTION_EMAIL


TICK_TIME_IN_SECONDS = 300

NUMBER_OF_BENIGN_SCRIPTS = 2
NUMBER_OF_GET_SET_FLAG_COMBOS = 1

LOG_PATH = "/tmp/gamebot.log"

logging.basicConfig(filename=LOG_PATH, level=logging.WARNING,
                    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S')


def main():
    user = MYSQL_DATABASE_USER
    db_name = MYSQL_DATABASE_DB
    password = MYSQL_DATABASE_PASSWORD

    db = MySQLdb.connect(user=user, passwd=password, db=db_name,
                         cursorclass=MySQLdb.cursors.DictCursor)

    c = db.cursor()

    current_tick, seconds_left = get_current_tick(c)
    if current_tick != 0:
        print "We must be picking up from the last run. Sleep for", seconds_left, \
              "until the next tick."
        time.sleep(seconds_left)

    team_ids = get_team_ids(c)
    service_ids = get_service_ids(c)

    while True:
        # Update containers that have been changed since last update
        print "Finding service containers that need to be updated"
        updated_containers = get_service_containers_needing_update(c)
        if updated_containers:
            print "%d containers need to be updated" % (len(updated_containers))
            update_service_containers(db, updated_containers)
            print "Updated %d containers" % (len(updated_containers))
        else:
            print "No service containers require updating"

        print "Finding exploit containers that need to be updated"
        updated_containers = get_exploit_containers_needing_update(c)
        if updated_containers:
            print "%d containers need to be updated" % (len(updated_containers))
            update_exploit_containers(db, updated_containers)
            print "Updated %d containers" % (len(updated_containers))
        else:
            print "No exploit containers require updating"

        # Create a new tick
        current = datetime.now()

        time_to_sleep = random.uniform(TICK_TIME_IN_SECONDS - 30, TICK_TIME_IN_SECONDS + 30)

        time_to_change = current + timedelta(seconds=time_to_sleep)
        c.execute("""insert into ticks (time_to_change, created_on) values(%s,
                  %s)""", (time_to_change.isoformat(), current.isoformat(),))
        tick_id = db.insert_id()

        print "tick", tick_id

        num_benign_scripts = random.randint(max(1, NUMBER_OF_BENIGN_SCRIPTS - 1),
                                            NUMBER_OF_BENIGN_SCRIPTS + 1)

        # Decide what scripts to run against each team
        for team_id in team_ids:
            list_of_scripts_to_execute = \
                get_list_of_scripts_and_exploits_to_run(c, service_ids,
                                                        num_benign_scripts)

            c.execute("""insert into team_scripts_run_status (team_id, tick_id,
                      json_list_of_scripts_to_run, created_on) values (%s, %s, %s,
                      %s)""", (team_id, tick_id,
                               json.dumps(list_of_scripts_to_execute),
                               datetime.now().isoformat()))

        # Commit everything to the db
        db.commit()

        # Sleep for the amount of time until the next tick

        time_diff_to_sleep = time_to_change - datetime.now()
        seconds_to_sleep = time_diff_to_sleep.seconds + (time_diff_to_sleep.microseconds/1E6)

        if time_diff_to_sleep.total_seconds() < 0:
            print time_diff_to_sleep
            seconds_to_sleep = 0

        print "Sleeping for", seconds_to_sleep
        time.sleep(seconds_to_sleep)
        print "Awake"


def get_service_containers_needing_update(cursor):
    containers_list = []
    cursor.execute("""select name, registry_namespace, image_name, team_id,
                   service_id from containers where update_required = True and type =
                   'Service'""")
    containers = cursor.fetchall()

    teams = {}
    cursor.execute("""select id, team_name from teams""")
    for row in cursor.fetchall():
        teams[row["id"]] = row["team_name"]

    services = {}
    cursor.execute("""select id, name from services""")
    for row in cursor.fetchall():
        services[row["id"]] = row["name"]

    cursor.execute("""select flags_storage_folder_host from game limit 1""")
    result = cursor.fetchone()
    flags_storage_folder = result["flags_storage_folder_host"]

    for container in containers:
        ret_container = {}
        for key in container:
            ret_container[key] = container[key]

        cursor.execute("""select host_ip, host_port from services_locations where
                       team_id = %s and service_id = %s limit 1""",
                       (container["team_id"], container["service_id"]))
        result = cursor.fetchone()
        ret_container["host_ip"] = result["host_ip"]
        ret_container["external_port"] = result["host_port"]

        cursor.execute("""select internal_port, workdir from services where
                       id = %s""", (container["service_id"], ))
        result = cursor.fetchone()
        ret_container["internal_port"] = result["internal_port"]
        ret_container["internal_flag_storage"] = result["workdir"]

        team = teams[container["team_id"]]
        service = services[container["service_id"]]
        ret_container["external_flag_storage"] = os.path.join(flags_storage_folder,
                                                              team, service)
        containers_list.append(ret_container)

    return containers_list


def get_exploit_containers_needing_update(cursor):
    cursor.execute("""select name, registry_namespace, image_name, team_id,
                   service_id from containers where update_required = True and type =
                   'Exploit'""")
    return cursor.fetchall()


def get_list_of_scripts_and_exploits_to_run(c, service_ids, num_benign_scripts):
    scripts_and_exploits_to_run = []

    # we want to run all the set flags first, then a random mix of benign and get flags
    set_flag_scripts = []
    get_flag_scripts = []
    benign_scripts = []

    for service_id in service_ids:
        c.execute("""select id, is_ours, type, team_id, service_id, is_working,
                  latest_script from scripts where service_id = %s and is_working = 1
                  and latest_script = 1""", (service_id,))
        results = c.fetchall()

        benigns = []
        for result in results:
            the_type = result['type']
            the_id = result['id']
            if the_type == 'getflag':
                get_flag_scripts.append({"id": the_id, "type": "script"})
            elif the_type == 'setflag':
                set_flag_scripts.append({"id": the_id, "type": "script"})
            elif the_type == 'benign':
                benigns.append({"id": the_id, "type": "script"})
            elif the_type == 'exploit':
                assert False, "In this version, we should never be running exploits"

        for _ in xrange(num_benign_scripts):
            if benigns:
                benign_script = random.choice(benigns)
                benign_scripts.append(benign_script)

    random.shuffle(set_flag_scripts)
    random.shuffle(get_flag_scripts)

    scripts_and_exploits_to_run.extend(set_flag_scripts)

    c.execute("""select id from containers where type='exploit'""")
    exploit_containers = [{"id": result["id"], "type": "exploit_container"} for
                          result in c.fetchall()]

    other_scripts = []
    other_scripts.extend(exploit_containers)
    other_scripts.extend(benign_scripts)
    random.shuffle(other_scripts)

    scripts_and_exploits_to_run.extend(other_scripts)
    scripts_and_exploits_to_run.extend(get_flag_scripts)

    return scripts_and_exploits_to_run


def get_team_ids(c):
    c.execute("""select id from teams""")

    return set(r['id'] for r in c.fetchall())


def get_service_ids(c):
    c.execute("""select id from services""")

    return set(r['id'] for r in c.fetchall())


def get_current_tick(c):
    c.execute("""select id, time_to_change, created_on from ticks order by created_on
              desc limit 1""")
    result = c.fetchone()
    current_tick = 0
    seconds_left = 0
    if result:
        current_tick = result['id']
        current_time = iso8601.parse_date(datetime.now().isoformat())
        time_to_change = iso8601.parse_date(result['time_to_change'])

        seconds_left = (time_to_change - current_time).total_seconds()
        if seconds_left < 0:
            seconds_left = 0

    return current_tick, seconds_left


def update_service_containers(db, containers):
    remote_clients = {}
    max_client_connect_retries = 3
    user = DOCKER_DISTRIBUTION_USER
    password = DOCKER_DISTRIBUTION_PASS
    email = DOCKER_DISTRIBUTION_EMAIL
    server = DOCKER_DISTRIBUTION_SERVER
    port_num = REMOTE_DOCKER_DAEMON_PORT
    cursor = db.cursor()
    for container in containers:
        host_ip = container['host_ip']
        if host_ip not in remote_clients:
            url = "tcp://%s:%d" % (host_ip, port_num)
            for _ in xrange(max_client_connect_retries):
                remote_clients[host_ip] = docker.Client(base_url=url)
                if remote_clients[host_ip].ping() == "OK":
                    break
            else:
                logging.error("Unable to connect to docker instance on %s:%s" %
                              (host_ip, port_num))
                return

        remote_client = remote_clients[host_ip]
        logging.info("Updating service container of service %d team %d on host %s" %
                     (container["service_id"], container["team_id"], host_ip))

        try:
            # Stop container
            remote_client.stop(container["name"])
            logging.info("Stopped container %s" % (container["name"],))
        except docker.errors.NotFound:
            logging.warning("No container %s found on %s when stopping" %
                            (container["name"], host_ip))

        try:
            # Delete container
            remote_client.remove_container(container["name"])
            logging.info("Removed container %s" % (container["name"]))
        except docker.errors.NotFound:
            logging.warning("No container %s found on %s when removing" %
                            (container["name"], host_ip))

        # Update image
        try:
            remote_client.login(username=user, password=password, email=email,
                                registry=server)
        except docker.errors.APIError, e:
            logging.error("Login to registry %s as %s failed" % (server, user))
            logging.error(e)
            continue

        image_url = '/'.join([server, container['registry_namespace'],
                              container['image_name']])
        try:
            output = list(remote_client.pull(image_url, stream=True))
        except docker.errors.APIError, e:
            logging.error("APIError when pulling image %s failed" % (image_url))
            logging.error(e)
            continue

        last_line_json = json.loads(output[-1])
        if 'Downloaded newer image' not in last_line_json['status'] and \
           'Image is up to date' not in last_line_json['status']:
            # Error!
            logging.error("Pulling image %s failed. Docker client output below." %
                          (image_url))
            logging.error("%s" % (output))
            continue

        # Create and start container
        port_mapping = {container['internal_port']: container['external_port']}
        folder_mappings = {
            container['external_flag_storage']: {
                'bind': container['internal_flag_storage'],
                'mode': 'rw'
                }
            }

        container_config = remote_client.create_host_config(binds=folder_mappings,
                                                            port_bindings=port_mapping)

        remote_client.create_container(image=image_url,
                                       ports=[container['internal_port']],
                                       name=container["name"],
                                       host_config=container_config)
        remote_client.start(container["name"])
        cursor.execute("""update containers set update_required = False where
                       team_id=%s and service_id=%s and type='Service'""",
                       (container["team_id"], container["service_id"]))
        db.commit()

    return


def update_exploit_containers(db, containers):
    max_client_connect_retries = 3
    user = DOCKER_DISTRIBUTION_USER
    password = DOCKER_DISTRIBUTION_PASS
    email = DOCKER_DISTRIBUTION_EMAIL
    server = DOCKER_DISTRIBUTION_SERVER
    port_num = REMOTE_DOCKER_DAEMON_PORT
    cursor = db.cursor()
    cursor.execute("""select exploit_containers_host from game limit 1""")
    result = cursor.fetchone()
    exploit_containers_host = result["exploit_containers_host"]
    url = "tcp://%s:%d" % (exploit_containers_host, port_num)
    remote_client = docker.Client(base_url=url)
    for _ in xrange(max_client_connect_retries):
        if remote_client.ping() == "OK":
            break
    else:
        logging.error("Unable to connect to docker instance on %s:%s" %
                      (exploit_containers_host, port_num))
        return

    for container in containers:
        logging.info("Updating exploit image of service %d team %d on host %s" %
                     (container["service_id"], container["team_id"],
                      exploit_containers_host))

        # Clean up just in case scorebot didn't do so after running exploit
        # Image update will fail otherwise
        try:
            # Stop container
            remote_client.stop(container["name"])
            logging.info("Stopped container %s" % (container["name"],))
        except docker.errors.NotFound:
            logging.warning("No container %s found on %s when stopping" %
                            (container["name"], exploit_containers_host))

        try:
            # Delete container
            remote_client.remove_container(container["name"])
            logging.info("Removed container %s" % (container["name"]))
        except docker.errors.NotFound:
            logging.warning("No container %s found on %s when removing" %
                            (container["name"], exploit_containers_host))

        # Update image
        try:
            remote_client.login(username=user, password=password, email=email,
                                registry=server)
        except docker.errors.APIError, e:
            logging.error("Login to registry %s as %s failed" % (server, user))
            logging.error(e)
            continue

        image_url = '/'.join([server, container['registry_namespace'],
                              container['image_name']])
        try:
            output = list(remote_client.pull(image_url, stream=True))
        except docker.errors.APIError, e:
            logging.error("APIError when pulling image %s failed" % (image_url))
            logging.error(e)
            continue

        last_line_json = json.loads(output[-1])
        if 'Downloaded newer image' not in last_line_json['status'] and \
           'Image is up to date' not in last_line_json['status']:
            # Error!
            logging.error("Pulling image %s failed. Docker client output below." %
                          (image_url))
            logging.error("%s" % (output))
            continue

        cursor.execute("""update containers set update_required = False where
                       team_id=%s and service_id=%s and type='Exploit'""",
                       (container["team_id"], container["service_id"]))
        db.commit()

    return


if __name__ == "__main__":
    sys.exit(main())
