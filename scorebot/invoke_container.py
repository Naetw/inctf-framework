#!/usr/bin/env python
# -*- coding: utf-8 -*-


# Standard library imports
import json
import logging
import os
import sys
import urllib

# Imports from third party packages
import docker
import requests

DB_SECRET = "YOUKNOWSOMETHINGYOUSUCK"
DOCKER_REGISTRY_SERVER = "localhost:5000"
KILL_TIMEOUT = 20  # seconds
LOG_PATH = "/tmp/container-invoker.log"
REMOTE_DOCKER_PORT = 2375
SUBMIT_SERVER = "localhost:4000"
STATUS_SERVER = SUBMIT_SERVER
WAIT_TIMEOUT = 60  # seconds

logging.basicConfig(filename=LOG_PATH, level=logging.INFO, filemode='a',
                    format='%(asctime)s, %(name)s, %(levelname)s, %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S')

logger = logging.getLogger("__INVOKE_CONTAINER__")


def main():
    logger.info("Starting exploit")
    arguments = ["CONTAINER_HOST", "CONTAINER_NAMESPACE", "CONTAINER_IMAGE",
                 "TARGET_IP", "TARGET_PORT", "SERVICE_ID", "CURRENT_FLAG_ID",
                 "ATTACKER_TEAM_ID", "DEFENDING_TEAM_ID"]
    if len(sys.argv) != len(arguments) + 1:
        print "Usage: %s %s" % (sys.argv[0], ' '.join(arguments))
        logger.error("Incorrect argument count. Received %d, expected %d." %
                     (len(sys.argv), len(arguments) + 1))
        sys.exit(0)

    container_host = sys.argv[1]
    namespace = sys.argv[2]
    image = sys.argv[3]
    target_host = sys.argv[4]
    target_port = int(sys.argv[5])
    service_id = int(sys.argv[6])
    flag_id = sys.argv[7]
    attacker = int(sys.argv[8])
    defender = int(sys.argv[9])
    logger.info("Image: %s, namespace: %s, target: (%s, %d)" %
                (image, namespace, target_host, target_port))
    max_connect_retries = 3
    url = "tcp://%s:%d" % (container_host, REMOTE_DOCKER_PORT)
    logger.info("Remote Docker URL: %s" % (url))

    client = docker.Client(base_url=url)
    for _ in xrange(max_connect_retries):
        if client.ping() == "OK":
            break
    else:
        logger.error("Unable to connect to remote docker instance at %s:%d" %
                     (container_host, REMOTE_DOCKER_PORT))
        sys.exit(1)

    env_vars = {"TARGET_HOST": str(target_host), "TARGET_PORT": str(target_port),
                "FLAG_ID": str(flag_id)}
    container_image = os.path.join(DOCKER_REGISTRY_SERVER, namespace, image)

    # Create container with service IP and PORT in env variables and start container.
    container = client.create_container(image=container_image, environment=env_vars)
    logger.info("Create container returned %s" % (container))
    client.start(container["Id"])

    try:
        # Wait till container times out
        exit_code = client.wait(container, WAIT_TIMEOUT)
        logger.info("Container exited with code %d" % (exit_code))
        stdout = client.logs(container=container, stdout=True, stderr=False).strip()
        stderr = client.logs(container=container, stderr=True, stdout=False).strip()
        logger.info("stdout: %s" % (stdout))
        logger.info("stderr: %s" % (stderr))
        flag = stdout.strip()
        logger.info("flag: %s" % (flag))
        flag_submit_url = "http://%s/submitflag/%d/%s?secret=%s" % \
                          (SUBMIT_SERVER, attacker, flag, DB_SECRET)
        logger.info("submission URL: %s" % (flag_submit_url))
        r = urllib.urlopen(flag_submit_url).read()
        response = json.loads(r)
        logger.info("Submit response: %s" % (r))
        if response["result"] == "correct":
            logger.info("Success!")
            attack_success = True
        else:
            logger.info("Failure!")
            attack_success = False
        logger.info("Inserting exploit status into DB")
        params = {
            'secret': DB_SECRET,
            'attack_success': attack_success,
            'attacker': attacker,
            'defender': defender,
            'service_id': service_id,
            'stdout': stdout,
            'stderr': stderr
            }
        logger.info("values to insert: %s" % (params))
        exploit_status_url = "http://%s/ranexploit?%s" % \
                             (STATUS_SERVER, urllib.urlencode(params))
        r = urllib.urlopen(exploit_status_url).read()
        logger.info("ranexploit returned %s" % (r))
    except requests.exceptions.ReadTimeout:
        logger.warning("Timeout when waiting for response from exploit container")
        logger.warning("Team ID: %d, Service ID: %d" % (attacker, service_id))
    finally:
        logger.info("Stopping and deleting container")
        try:
            client.stop(container["Id"], KILL_TIMEOUT)
        except docker.errors.NotFound:
            # Container has probably already exited.
            logger.info("Container not found: probably exited on it's own")
            pass

        client.remove_container(container["Id"])
        logger.info("""Container stopped and removed successfully. Closing remote
                    client.""")
        client.close()


if __name__ == "__main__":
    main()
