#!/usr/bin/env python
# -*- coding: utf-8 -*-


# "Standard library imports"
import argparse
import json
import os
import shutil
import sys


def create_links_to_debs_and_image(services, services_dir, image, dst_dir):
    for service in services:
        src_file = os.path.join(services_dir, service + ".deb")
        dst_file = os.path.join(dst_dir, service, service + ".deb")
        os.link(src_file, dst_file)
        image_dst_file = os.path.join(dst_dir, service, os.path.basename(image))
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
    return parser


def create_output_dirs_for_services(services, destination):
    os.mkdir(destination)
    for service in services:
        os.mkdir(os.path.join(destination, service))

    return


def generate_dockerfiles(services, image_name, output_dir, dockerfile_template):
    data = {}
    data['image'] = image_name
    for service in services:
        print "Generating Dockerfile for %s..." % (service),
        os.chdir(os.path.join(output_dir, service))
        data['deb_file'] = service + ".deb"
        for key in ["user", "workdir"]:
            data[key] = services[service][key]

        data["cmd"] = [services[service]["command"]]
        if "args" in services[service]:
            data["cmd"].extend(services[service]["args"])

        dockerfile_fh = open("Dockerfile", 'w')
        dockerfile_fh.write(dockerfile_template.format(**data))
        dockerfile_fh.close()
        print "done"

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

    return


def validate_services_config(services, services_dir):
    for service in services:
        if not os.path.isfile(os.path.join(services_dir, service + ".deb")):
            print "Could not find %s.deb in %s. Exiting!" % (service, services_dir)
            sys.exit(1)

    necessary_keys = ["user", "workdir", "command"]
    for service in services:
        keys = services[service].keys()
        for necessary_key in necessary_keys:
            if necessary_key not in keys:
                print "%s not provided for service %s in config. Exiting!" % \
                    (necessary_key, service)
                sys.exit(1)

    return


def main():
    parser = create_argument_parser()
    args = parser.parse_args()
    test_arguments(args)
    config_file = args.config
    image_file = args.image
    services_dir = args.services_location
    output_dir = os.path.realpath(args.output_dir)
    if os.path.exists(output_dir):
        print "%s exists. Deleting and recreating directory." % (output_dir)
        shutil.rmtree(output_dir)

    dockerfile_template_file = os.path.join(os.getcwd(), "Dockerfile.template")
    if not os.path.isfile(dockerfile_template_file):
        print "Could not find %s. Exiting!" % (dockerfile_template_file)
        sys.exit(1)

    template_fh = open(dockerfile_template_file)
    dockerfile_template = template_fh.read()
    template_fh.close()
    config_file_fh = open(config_file)
    contents = config_file_fh.read()
    config_file_fh.close()

    try:
        configuration = json.loads(contents)
    except ValueError, e:
        print ("Error when reading config from %s: " + e.message) % (config_file)
        sys.exit(1)

    services = {}
    for service in configuration["services"]:
        services[service["service_name"]] = service

    validate_services_config(services, services_dir)
    create_output_dirs_for_services(services, output_dir)
    create_links_to_debs_and_image(services, services_dir, image_file, output_dir)
    generate_dockerfiles(services, os.path.basename(image_file),
                         output_dir, dockerfile_template)
    return


if __name__ == "__main__":
    main()
