#!/usr/bin/env python
# -*- coding: utf-8 -*-


# "Standard library imports"
import argparse
import json
import os
import shutil
import sys


def copy_debs_and_image(services, directory, image):
    debs_tmp_dir = "tmp"
    if not os.path.isdir(debs_tmp_dir):
        os.mkdir(debs_tmp_dir)

    for service in services:
        shutil.copy2(os.path.join(directory, service), debs_tmp_dir)

    shutil.copy2(image, os.getcwd())
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


def main():
    parser = create_argument_parser()
    args = parser.parse_args()
    test_arguments(args)
    config_file = args.config
    image_file = args.image
    services_dir = args.services_location
    output_dir = args.output
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.getcwd(), output_dir)

    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)

    os.mkdir(output_dir)

    config_file_fh = open(config_file)
    contents = config_file_fh.read()
    config_file_fh.close()

    try:
        configuration = json.loads(contents)
    except ValueError, e:
        print ("Error when reading config from %s: " + e.message) % (config_file)
        sys.exit(1)

    services = configuration["services"]

    for service in services:
        if not os.path.isfile(os.path.join(services_dir, service + ".deb")):
            print "Could not find %s.deb in %s. Exiting!" % (service, services_dir)
            sys.exit(1)

    copy_debs_and_image(services, services_dir, image_file)
    return


if __name__ == "__main__":
    main()
