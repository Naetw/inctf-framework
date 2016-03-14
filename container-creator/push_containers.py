#!/usr/bin/env python
# -*- coding: utf-8 -*-


# "Standard library imports"
import argparse
import json
import os
import subprocess
import sys

# "Imports from current project"
from create_containers import generate_service_containers_config


def create_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-sl", "--services-location", type=str, required=True,
                        help="Folder where deb archives are stored")
    parser.add_argument("-c", "--config", type=str, required=True,
                        help="""Configuration file containing info about contest
                        such as name, team names and names of services""")
    parser.add_argument("-ds", "--distribution-server", type=str, required=True,
                        help="""Server running Docker distribution""")
    parser.add_argument("-dpo", "--distribution-port", type=int, required=True,
                        help="""Port to connect to Docker distribution""")
    parser.add_argument("-du", "--distribution-user", type=str, required=True,
                        help="""Username of gameserver in Docker distribution""")
    parser.add_argument("-dpass", "--distribution-pass", type=str, required=True,
                        help="""Password of gameserver user""")
    parser.add_argument("-de", "--distribution-email", type=str, required=True,
                        help="""Email ID of gameserver user""")
    return parser


def push_all_containers_to_distribution(teams, services, creds):
    containers_config = generate_service_containers_config(services, teams)
    server = ':'.join([creds["server"], str(creds["port"])])
    print "Creating tags for all services of all teams"
    tags_to_push = []
    for config in containers_config:
        tag = '/'.join([server, config["namespace"], config["image_name"]])
        command = ["docker", "tag", config["service"], tag]
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print "Tagging image for team %s, service %s failed" % \
                  (config["team"], config["service"])
            print "Stdout: %s" % (stdout)
            print "Stderr: %s" % (stderr)
        else:
            tags_to_push.append(tag)

    print "%d tags to push" % (len(tags_to_push))
    print "Generating shell script to push tags to server"
    script_file_name = "push_tags.sh"
    fh = open(script_file_name, 'w')
    for _ in xrange(3):
        fh.write("docker login -u %s -p %s -e \"%s\" %s" %
                 (creds["user"], creds["pass"], creds["email"], server))
        fh.write(os.linesep)

    total = len(tags_to_push)
    for tag_id in xrange(len(tags_to_push)):
        fh.write('echo "Pushing %d of %d"' % (tag_id + 1, total))
        tag = tags_to_push[tag_id]
        for _ in xrange(3):
            fh.write(os.linesep)
            fh.write("docker push %s" % (tag))
            fh.write(os.linesep)

    fh.close()
    os.system("sh ./%s" % (script_file_name))
    os.remove(script_file_name)
    return


def main():
    parser = create_argument_parser()
    args = parser.parse_args()
    config_file = args.config
    services_dir = args.services_location

    config_file_fh = open(config_file)
    contents = config_file_fh.read()
    config_file_fh.close()

    try:
        configuration = json.loads(contents)
    except ValueError, e:
        print ("Error when reading config from %s: " + e.message) % (config_file)
        sys.exit(1)
    teams = configuration["teams"]
    services = []
    for service_name in configuration["services"]:
        service_info_fh = open(os.path.join(services_dir, service_name, "info.json"))
        services.append(json.load(service_info_fh))
        service_info_fh.close()

    registry_config = {"server": args.distribution_server,
                       "port": args.distribution_port,
                       "user": args.distribution_user,
                       "pass": args.distribution_pass,
                       "email": args.distribution_email
                       }
    push_all_containers_to_distribution(teams, services, registry_config)


if __name__ == "__main__":
    main()
