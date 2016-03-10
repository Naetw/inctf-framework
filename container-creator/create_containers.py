#!/usr/bin/env python
# -*- coding: utf-8 -*-


# "Standard library imports"
import argparse
import json
import os
import shutil
import stat
import subprocess
import sys


def build_images(services, container_config_dir):
    for service in services:
        print "Building container image for service %s" % (service["name"])
        command = ["docker", "build", "-t", service["name"],
                   os.path.join(container_config_dir, service["name"])]
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            print "Something went wrong when building image of %s" % (service["name"])
            print "Stdout: %s" % (stdout)
            print "Stderr: %s" % (stderr)
        else:
            print "Built image for service %s with tag %s" % (service["name"], service["name"])

    return


def create_links_to_debs_and_image(services, services_dir, image, dst_dir):
    for service in services:
        src_file = os.path.join(services_dir, service["name"] + ".deb")
        dst_file = os.path.join(dst_dir, service["name"], service["name"] + ".deb")
        os.link(src_file, dst_file)
        image_dst_file = os.path.join(dst_dir, service["name"], os.path.basename(image))
        os.link(image, image_dst_file)

    return


def create_argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("-sl", "--services-location", type=str, required=True,
                        help="Folder where deb archives are stored")
    parser.add_argument("-i", "--image", type=str, required=True,
                        help="Path to OS base image for container. For Ubuntu " +
                        "images, visit http://cloud-images.ubuntu.com/")
    parser.add_argument("-c", "--config", type=str, required=True,
                        help="Configuration file containing info about contest " +
                        "such as name, team names and names of services")
    parser.add_argument("-od", "--output-dir", type=str, default="output",
                        help="Directory to output Dockerfile and other files")
    parser.add_argument("--apt-proxy-host", type=str, help="IP address of APT proxy")
    parser.add_argument("--apt-proxy-port", type=int, help="Port used by APT proxy")
    return parser


def create_output_dirs_for_services(services, destination):
    for service in services:
        os.mkdir(os.path.join(destination, service["name"]))

    return


def generate_dockerfiles(services, image_name, output_dir, dockerfile_template,
                         commands_template, proxy_host=None, proxy_port=None):
    data = {}
    data['image'] = image_name
    commands_file = "commands.sh"
    dockerfile = "Dockerfile"
    for service in services:
        print "Generating Dockerfile for %s..." % (service["name"]),
        os.chdir(os.path.join(output_dir, service["name"]))
        data['deb_file'] = service["name"] + ".deb"
        for key in ["user", "workdir"]:
            data[key] = service[key]

        data["cmd"] = [service["command"]]
        if "args" in service:
            data["cmd"].extend(service["args"])

        data["cmd"] = json.dumps(data["cmd"])

        if "pre_install" in service:
            data["pre_install"] = os.linesep.join(service["pre_install"])
        else:
            data["pre_install"] = os.linesep

        if "post_install" in service:
            data["post_install"] = os.linesep.join(service["post_install"])
        else:
            data["post_install"] = os.linesep

        if proxy_host:
            activate_proxy_cmd = "echo 'Acquire::http { Proxy \"http://" + \
                proxy_host + ":" + str(proxy_port) + "\"; };' > /etc/apt/apt.conf.d/02proxy"
            deactivate_proxy_cmd = "truncate --size 0 /etc/apt/apt.conf.d/02proxy"
            data["pre_install"] = data["pre_install"] + os.linesep + \
                activate_proxy_cmd
            data["post_install"] = data["post_install"] + os.linesep + \
                deactivate_proxy_cmd

        dockerfile_fh = open(dockerfile, 'w')
        dockerfile_fh.write(dockerfile_template.format(**data))
        dockerfile_fh.close()

        commands_file_fh = open(commands_file, 'w')
        commands_file_fh.write(commands_template.format(**data))
        commands_file_fh.close()
        os.chmod(commands_file, os.stat(commands_file).st_mode | stat.S_IEXEC)

        print "done"

    return


def generate_service_containers_config(services, teams):
    config = []
    for service in services:
        for team in teams:
            team_configuration = {}
            team_configuration["name"] = "service_" + service["name"] + "_" + \
                                         team["name"]
            team_configuration["image_name"] = "service_" + service["name"]
            team_configuration["namespace"] = team["namespace"]
            team_configuration["team"] = team["name"]
            team_configuration["service"] = service["name"]
            team_configuration["type"] = "SERVICE"
            config.append(team_configuration)

    return config


def generate_services_config(services):
    configs = []
    required_info = ["name", "internal_port", "description", "authors",
                     "flag_id_description"]
    custom_key_mappings = {}
    custom_key_mappings["internal_port"] = "port"
    custom_key_mappings["description"] = "service_description"
    current_offset = 0
    for service in services:
        service_config = {}
        for info in required_info:
            if info in custom_key_mappings:
                service_config[info] = service[custom_key_mappings[info]]
            else:
                service_config[info] = service[info]

        service_config["offset_external_port"] = current_offset
        current_offset = current_offset + 1
        configs.append(service_config)

    return configs


def generate_scripts_config(services):
    configs = []
    for service in services:
        for key in ["getflag", "setflag"]:
            script_config = {}
            script_config["type"] = key
            script_config["name"] = os.path.basename(service[key])
            script_config["service"] = service["name"]
            script_config["is_working"] = 1
            configs.append(script_config)

        for script in service["benign"]:
            script_config = {}
            script_config["type"] = "benign"
            script_config["name"] = os.path.basename(script)
            script_config["service"] = service["name"]
            script_config["is_working"] = 1
            configs.append(script_config)

    return configs


def generate_teams_config(teams, services_count, host, start_port):
    configs = []
    next_start_port = start_port
    for team in teams:
        team_config = {}
        team_config["name"] = team["name"]
        team_config["services_ports_low"] = next_start_port
        next_start_port = next_start_port + services_count
        team_config["services_ports_high"] = next_start_port - 1
        configs.append(team_config)

    return configs


def generate_location_config(services, teams, host):
    configs = []
    for team in teams:
        for service in services:
            config = {}
            config["team"] = team["name"]
            config["service"] = service["name"]
            config["host_ip"] = host
            config["host_port"] = team["services_ports_low"] + \
                service["offset_external_port"]
            assert config["host_port"] <= team["services_ports_high"]
            configs.append(config)

    return configs


def generate_initial_db_config(services, teams, containers_host,
                               containers_ports_start, db_dir):
    print "Generating DB configuration"
    db_config_file = os.path.join(db_dir, "initial_db_state.json")

    db_config = {}
    db_config["containers"] = generate_service_containers_config(services, teams)
    db_config["teams"] = generate_teams_config(teams, len(services), containers_host,
                                               containers_ports_start)
    db_config["services"] = generate_services_config(services)
    db_config["services_location"] = generate_location_config(db_config["services"],
                                                              db_config["teams"],
                                                              containers_host)
    db_config["scripts"] = generate_scripts_config(services)
    db_config["exploit_containers_host"] = containers_host
    db_config_fh = open(db_config_file, 'w')
    json.dump(db_config, db_config_fh, indent=4, separators=(',', ': '))
    db_config_fh.close()
    print "Wrote DB configuration to %s" % (db_config_file)
    return


def test_arguments(args):
    if not os.path.isfile(args.config):
        print "Cannot find file %s. Exiting!" % (args.config)
        sys.exit(1)

    if not os.path.isfile(args.image):
        print "Could not find image file %s. Exiting!" % (args.image)
        sys.exit(1)

    if not os.path.isdir(args.services_location):
        print "%d is not a valid directory. Exiting!" % (args.services_location)
        sys.exit(1)

    if args.apt_proxy_host is None and args.apt_proxy_port is not None:
        print "APT proxy port specified but no host specified. Exiting!"
        sys.exit(1)

    if args.apt_proxy_port is None and args.apt_proxy_host is not None:
        print "APT proxy host specified but no port specified. Exiting!"
        sys.exit(1)

    return


def validate_services_config(services, services_dir):
    necessary_keys = ["user", "workdir", "command", "port", "authors", "name"]
    for service in services:
        keys = service.keys()
        for necessary_key in necessary_keys:
            if necessary_key not in keys:
                print "%s not provided for service %s in config. Exiting!" % \
                    (necessary_key, service["name"])
                sys.exit(1)

        if not os.path.isfile(os.path.join(services_dir, service["name"] + ".deb")):
            print "Could not find %s.deb in %s. Exiting!" % (service["name"], services_dir)
            sys.exit(1)

    return


def main():
    parser = create_argument_parser()
    args = parser.parse_args()
    test_arguments(args)
    config_file = args.config
    image_file = args.image
    services_dir = args.services_location
    apt_proxy_host = args.apt_proxy_host
    apt_proxy_port = args.apt_proxy_port

    dockerfile_template_file = os.path.join(os.getcwd(), "Dockerfile.template")
    if not os.path.isfile(dockerfile_template_file):
        print "Could not find %s. Exiting!" % (dockerfile_template_file)
        sys.exit(1)

    template_fh = open(dockerfile_template_file)
    dockerfile_template = template_fh.read()
    template_fh.close()

    commands_template_file = os.path.join(os.getcwd(), "commands.sh.template")
    if not os.path.isfile(commands_template_file):
        print "Could not find %s. Exiting!" % (commands_template_file)
        sys.exit(1)

    template_fh = open(commands_template_file)
    commands_template = template_fh.read()
    template_fh.close()

    config_file_fh = open(config_file)
    contents = config_file_fh.read()
    config_file_fh.close()

    try:
        configuration = json.loads(contents)
    except ValueError, e:
        print ("Error when reading config from %s: " + e.message) % (config_file)
        sys.exit(1)

    game_name = configuration["name"]
    output_dir = os.path.join(os.path.realpath(args.output_dir), game_name)
    if os.path.exists(output_dir):
        print "%s exists. Deleting directory." % (output_dir)
        shutil.rmtree(output_dir)

    os.makedirs(output_dir)

    teams = configuration["teams"]
    container_host = configuration["containers_host"]
    containers_ports_start = configuration["containers_ports_start"]
    services = []
    for service_name in configuration["services"]:
        service_info_fh = open(os.path.join(services_dir, service_name, "info.json"))
        services.append(json.load(service_info_fh))
        service_info_fh.close()

    validate_services_config(services, services_dir)
    create_output_dirs_for_services(services, output_dir)
    create_links_to_debs_and_image(services, services_dir, image_file, output_dir)
    generate_dockerfiles(services, os.path.basename(image_file),
                         output_dir, dockerfile_template, commands_template,
                         apt_proxy_host, apt_proxy_port)
    build_images(services, output_dir)
    generate_initial_db_config(services, teams, container_host,
                               containers_ports_start, output_dir)
    return


if __name__ == "__main__":
    main()
