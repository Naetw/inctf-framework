#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Standard library imports
import json
import logging
import sys
import time
import urllib

# Imports from third party packages
import docker

# Imports from current project
from settings import DB_HOST, DB_SECRET

DOCKER_REGISTRY_SERVER = "localhost:5000"
KILL_TIMEOUT = None
LOG_PATH = "/tmp/container-invoker.log"
REMOTE_DOCKER_PORT = 2375
SUBMIT_SERVER = DB_HOST
STATUS_SERVER = SUBMIT_SERVER
WAIT_TIMEOUT = None

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, filemode='a',
                    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S')

logger = logging.getLogger("__INVOKE_CONTAINER__")


def get_team_name(team_id):
    url = "http://%s/teams?secret=%s" % (STATUS_SERVER, DB_SECRET)
    teams = json.loads(urllib.urlopen(url).read())
    for team in teams:
        if team["team_id"] == team_id:
            return team["team_name"]

    return None


def get_service_name(service_id):
    url = "http://%s/services?secret=%s" % (STATUS_SERVER, DB_SECRET)
    services = json.loads(urllib.urlopen(url).read())
    for service in services:
        if service["service_id"] == service_id:
            return service["service_name"]

    return None


def process_exited_container(container, state, attacker, env_vars, target,
                             service_id, client, team_logger):
    exit_code = state['State']['ExitCode']
    team_logger.info("Container exited with code %d" % (exit_code))
    stdout = client.logs(container=container, stdout=True, stderr=False).strip()
    stderr = client.logs(container=container, stderr=True, stdout=False).strip()
    team_logger.info("stdout: %s" % (stdout))
    team_logger.info("stderr: %s" % (stderr))
    flag = stdout.strip()
    team_logger.info("flag: %s" % (flag))
    flag_submit_url = "http://%s/submitflag/%d/%s?secret=%s" % \
                      (SUBMIT_SERVER, attacker, flag, DB_SECRET)
    team_logger.info("submission URL: %s" % (flag_submit_url))
    try:
        r = urllib.urlopen(flag_submit_url).read()
        response = json.loads(r)
        team_logger.info("Submit response: %s" % (r))
        if response["result"] == "correct":
            team_logger.info("Flag accepted!")
            attack_success = True
        else:
            team_logger.info("Flag not accepted! Reason: %s" % (response["result"]))
            attack_success = False
    except Exception, e:
        team_logger.error("Flag submission failed: %s. Target: %s" %
                          (str(e), env_vars))
        attack_success = False

    team_logger.info("Inserting exploit status into DB")
    params = {
        'secret': DB_SECRET,
        'attack_success': attack_success,
        'attacker': attacker,
        'defender': target["team_id"],
        'service_id': service_id,
        'stdout': stdout,
        'stderr': stderr
        }
    team_logger.info("values to insert: %s" % (params))
    exploit_status_url = "http://%s/ranexploit?%s" % \
                         (STATUS_SERVER, urllib.urlencode(params))
    r = urllib.urlopen(exploit_status_url).read()
    team_logger.info("ranexploit returned %s" % (r))
    client.remove_container(container["Id"])
    team_logger.info("""Container deleted. env_vars: %s""" % (env_vars, ))
    return


def main():
    logger.info("Starting exploit")
    arguments = ["CONTAINER_HOST", "CONTAINER_NAMESPACE", "CONTAINER_IMAGE",
                 "ATTACKER_TEAM_ID", "SERVICE_ID", "TARGETS", "ROUND_DURATION"]
    if len(sys.argv) != len(arguments) + 1:
        print "Usage: %s %s" % (sys.argv[0], ' '.join(arguments))
        logger.error("Incorrect argument count. Received %d, expected %d." %
                     (len(sys.argv), len(arguments) + 1))
        sys.exit(0)

    container_host = sys.argv[1]
    namespace = sys.argv[2]
    image = sys.argv[3]
    attacker = int(sys.argv[4])
    service_id = int(sys.argv[5])
    duration = float(sys.argv[7])
    WAIT_TIMEOUT = 0.3 * duration
    KILL_TIMEOUT = 0.2 * duration
    attacker_name = get_team_name(attacker)
    service_name = get_service_name(service_id)
    team_logger = logging.getLogger("__%s_attacking_%s__" %
                                    (attacker_name, service_name))
    team_logger.info("Total duration: %f, wait: %f, kill: %f" %
                     (duration, WAIT_TIMEOUT, KILL_TIMEOUT))

    try:
        targets = json.loads(sys.argv[6])
    except ValueError:
        team_logger.error("Invalid JSON targets string: %s" % (sys.argv[6]))
        sys.exit(1)

    team_logger.info("Image: %s, namespace: %s, targets: %s" %
                     (image, namespace, json.dumps(targets)))
    max_connect_retries = 3
    url = "tcp://%s:%d" % (container_host, REMOTE_DOCKER_PORT)
    team_logger.info("Remote Docker URL: %s" % (url))

    client = docker.Client(base_url=url)
    for _ in xrange(max_connect_retries):
        if client.ping() == "OK":
            break
    else:
        team_logger.error("Unable to connect to remote docker instance at %s:%d" %
                          (container_host, REMOTE_DOCKER_PORT))
        sys.exit(1)

    containers = []
    for target in targets:
        env_vars = {"TARGET_HOST": target["ip"], "TARGET_PORT": target["port"],
                    "FLAG_ID": target["flag_id"]}
        container_image = '/'.join([DOCKER_REGISTRY_SERVER, namespace, image])

        # Create container with service IP and PORT in env variables and start container.
        container = client.create_container(image=container_image, environment=env_vars)
        team_logger.info("Create container returned %s" % (container))
        client.start(container["Id"])
        entry = {'container': container, 'env_vars': env_vars, 'target': target}
        containers.append(entry)

    # Sleep for WAIT_TIMEOUT before checking container status
    team_logger.info("Containers list: %s" % (containers))
    team_logger.info("Sleeping for %d seconds" % (WAIT_TIMEOUT))
    time.sleep(WAIT_TIMEOUT)
    team_logger.info("Awake! Checking exploit containers.")

    non_exited_containers = []
    for entry in containers:
        team_logger.info("Processing entry %s. Fetching state" % (entry))
        container = entry["container"]
        # Process all exited containers
        state = client.inspect_container(container["Id"])
        team_logger.info("Fetched state of entry %s." % (entry))
        if state['State']['Status'] == 'exited':
            team_logger.info("Container %s has exited. Processing." %
                             (container["Id"]))
            process_exited_container(container, state, attacker, entry['env_vars'],
                                     entry['target'], service_id, client,
                                     team_logger)
        else:
            team_logger.info("Container %s has not exited. Defer processing." %
                             (container["Id"]))
            non_exited_containers.append(entry)

    if len(non_exited_containers) != 0:
        team_logger.info("%d containers not exited. Will be processed after %d seconds" %
                         (len(non_exited_containers), KILL_TIMEOUT))
        # Sleep for KILL_TIMEOUT before processing non-exited containers
        time.sleep(KILL_TIMEOUT)
        team_logger.info("Awake! Killing remaining containers!")
        # Process non-exited containers
        for entry in non_exited_containers:
            team_logger.info("Killing container %s." % (entry))
            container = entry["container"]
            client.stop(container["Id"], 0)
            team_logger.info("Fetching state of %s" % (entry))
            state = client.inspect_container(container["Id"])
            team_logger.info("Fetched state. Processing entry %s" % (entry))
            process_exited_container(container, state, attacker, entry['env_vars'],
                                     entry['target'], service_id, client,
                                     team_logger)
    else:
        team_logger.info("All containers exited successfully!")

    team_logger.info("Closing docker client.")
    client.close()
    return


if __name__ == "__main__":
    main()
