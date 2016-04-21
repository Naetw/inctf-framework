#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Standard library imports
import json
import logging
import sys
import urllib

# Imports from third party packages
import docker
import requests

# Imports from current project
from settings import DB_HOST, DB_SECRET

DOCKER_REGISTRY_SERVER = "linux-zrbf.suse:5000"
KILL_TIMEOUT = 0
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
    WAIT_TIMEOUT = 0.9 * duration
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

    env_vars = {"TARGETS": json.dumps(targets)}
    container_image = '/'.join([DOCKER_REGISTRY_SERVER, namespace, image])

    # Create container with service IP and PORT in env variables and start container.
    container = client.create_container(image=container_image, environment=env_vars)
    team_logger.info("Create container returned %s" % (container))
    client.start(container["Id"])

    try:
        # Wait till container times out
        exit_code = client.wait(container, WAIT_TIMEOUT)
        team_logger.info("Container exited with code %d" % (exit_code))
    except requests.exceptions.ReadTimeout:
        team_logger.warning("""Timeout when waiting for response from exploit
                            container. Team: %d, service: %d. Stopping.""" %
                            (attacker, service_id))
        client.stop(container["Id"], KILL_TIMEOUT)
    finally:
        stdout = client.logs(container=container, stdout=True, stderr=False).strip()
        stderr = client.logs(container=container, stderr=True, stdout=False).strip()
        team_logger.info("stdout: %s" % (stdout))
        team_logger.info("stderr: %s" % (stderr))
        flags = filter(lambda x: x != '', map(lambda x: x.strip(), stdout.split()))
        team_logger.info("flags: %s" % (flags))
        params = {
            'secret': DB_SECRET,
            'flags': json.dumps(flags),
            }
        flag_submit_url = "http://%s/submitflags/%d?%s" % \
                          (SUBMIT_SERVER, attacker, urllib.urlencode(params))
        team_logger.info("submission URL: %s" % (flag_submit_url))
        flag_submit_details = {'correct': 0, 'incorrect': 0, 'self': 0, 'duplicate': 0,
                               'points': 0}
        for _ in xrange(3):
            try:
                r = urllib.urlopen(flag_submit_url).read()
                flag_submit_details = json.loads(r)
                team_logger.info("Submit response: %s" % (r))
                break
            except Exception, e:
                team_logger.error("""Got error when submitting flag: %s. Trying
                                    again.""" % (str(e)))
                continue

        team_logger.info("Inserting exploit status into DB")
        params = {
            'secret': DB_SECRET,
            'service_id': service_id,
            'attacker': attacker,
            'stdout': stdout,
            'stderr': stderr
            }
        params.update(flag_submit_details)
        params['total'] = len(targets)

        team_logger.info("values to insert: %s" % (params))
        for _ in xrange(5):
            try:
                exploit_status_url = "http://%s/ranexploit?%s" % \
                                     (STATUS_SERVER, urllib.urlencode(params))
                r = urllib.urlopen(exploit_status_url).read()
                team_logger.info("ranexploit returned %s" % (r))
                break
            except Exception, e:
                team_logger.error("""Error when inserting exploit logs: %s. Trying
                                    again.""" % (str(e)))

        client.remove_container(container["Id"])
        team_logger.info("""Container removed successfully. Closing remote client.""")
        client.close()

    return


if __name__ == "__main__":
    main()
